# Draft News Crawler Data Pipeline Strategy

## 目的

このプロジェクトのデータ管理方針を、Google Sheets中心からSupabase中心へ移行する。

方針は次の通り。

- Supabaseを正本とする。
- Google Sheetsはレビュー用ビューとして残す。
- スクレイピング記事、選手候補、スカウトコメント、注目度シグナル、Draft-Watch記事候補をDBで管理する。
- Sheetsへの出力は、人間が確認する価値があるものに限定する。

## 現状

現在の処理は大きく次の流れになっている。

1. 各媒体から記事を取得する。
2. Google Sheetsの `Articles` から既存URLを取得して重複除外する。
3. 記事本文からスカウトコメント候補・注目度候補を判定する。
4. スカウトコメント候補記事のみGeminiでコメント抽出する。
5. 抽出したスカウトコメントをSupabaseの `scout_comments` に保存する。
6. 全記事・スカウトコメント・注目度シグナルをGoogle Sheetsへ出力する。

この構成では、Sheetsが重複判定と目視確認の両方を担っている。

## 既存の `public.articles` について

既にSupabaseには `public.articles` テーブルがある。

このテーブルは次の特徴を持つ。

- `slug` が必須かつunique。
- `type` は `news` または `column`。
- `category` は公開記事向けの制約を持つ。
- `content`, `excerpt`, `meta_title`, `is_published` など、Draft-Watch上で公開する記事を表すカラムがある。

そのため、このテーブルは **Draft-Watchで公開する記事本体** として扱うべきである。

クローラーが取得した生記事の保存・重複判定に `public.articles` を直接使うのは避ける。

理由:

- 外部ニュース記事にはDraft-Watch用の `slug` を必ずしも作る必要がない。
- 外部ニュース記事のカテゴリは、公開記事用カテゴリ制約と一致しない可能性がある。
- 生記事と公開記事を同じテーブルに混ぜると、未公開の外部記事とDraft-Watch下書きの区別が曖昧になる。
- 将来的に複数記事を統合して1本のDraft-Watch記事を作る場合、生記事と生成記事は多対1になる。

## 推奨テーブル構成

### 1. `crawled_articles`

外部媒体から取得した生記事を保存する。

用途:

- URL重複判定
- 本文保存
- スカウトコメント・注目度・選手候補抽出の元データ
- Draft-Watch記事候補生成時の出典

推奨カラム:

```sql
create table public.crawled_articles (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  category text null,
  url text not null unique,
  title text not null,
  body text null,
  published_at timestamp with time zone null,
  has_scout_comment_candidate boolean not null default false,
  has_attention_candidate boolean not null default false,
  has_player_candidate boolean not null default false,
  content_hash text null,
  raw jsonb null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);
```

実装メモ:

- 既存のSheets URL重複チェックは、このテーブルの `url` unique と `select url` に置き換える。
- `body` は全文保存する。
- `raw` にはスクレイパーの元データや抽出前の補助情報を保存してよい。

### 2. `player_candidates`

記事から抽出された未登録選手候補を保存する。

用途:

- `players` に未登録の選手を仮登録する。
- AI抽出ミスや表記揺れを人間が確認する。
- 信頼度が高いものだけ `players` に昇格する。

推奨カラム:

```sql
create table public.player_candidates (
  id uuid primary key default gen_random_uuid(),
  player_id uuid null,
  name text not null,
  name_kana text null,
  team_name text null,
  school_year text null,
  position text null,
  throws text null,
  bats text null,
  height_cm integer null,
  weight_kg integer null,
  birth_date date null,
  source_url text not null,
  source_title text null,
  evidence text null,
  confidence numeric null,
  status text not null default 'pending',
  extracted_raw jsonb null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint player_candidates_status_check check (
    status = any (array['pending', 'approved', 'rejected', 'promoted'])
  )
);
```

推奨index:

```sql
create index idx_player_candidates_name on public.player_candidates (name);
create index idx_player_candidates_status on public.player_candidates (status);
create unique index idx_player_candidates_unique_source
  on public.player_candidates (name, coalesce(team_name, ''), source_url);
```

運用方針:

- 最初は `players` へ直接INSERTしない。
- `player_candidates.status = pending` として保存する。
- 人間確認後、または高信頼度条件を満たした場合のみ `players` へ昇格する。

### 3. `attention_signals`

視察球団数・人数・球団名・注目度を保存する。

用途:

- Draft-Watch記事化候補の判定
- 選手の注目度蓄積
- 「12球団視察」「8球団以上」「MLB視察あり」などの抽出

推奨カラム:

```sql
create table public.attention_signals (
  id uuid primary key default gen_random_uuid(),
  crawled_article_id uuid null references public.crawled_articles(id),
  source_url text not null,
  source_title text null,
  published_at timestamp with time zone null,
  source text null,
  category text null,
  team_count integer not null default 0,
  person_count integer not null default 0,
  teams text[] not null default array[]::text[],
  has_npb boolean not null default false,
  has_mlb boolean not null default false,
  score integer not null default 0,
  evidence text not null,
  created_at timestamp with time zone not null default now()
);
```

### 4. `draft_watch_article_candidates`

Draft-Watchで記事化したい候補を保存する。

用途:

- 重要ニュースの下書き化
- 複数記事の統合
- スカウトコメント・視察情報をまとめた記事の生成

推奨カラム:

```sql
create table public.draft_watch_article_candidates (
  id uuid primary key default gen_random_uuid(),
  topic_type text not null,
  main_player_id uuid null,
  main_player_name text null,
  title text not null,
  importance_score integer not null default 0,
  source_urls text[] not null default array[]::text[],
  summary_json jsonb null,
  draft_article_markdown text null,
  status text not null default 'draft',
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint draft_watch_article_candidates_status_check check (
    status = any (array['draft', 'reviewed', 'published', 'rejected'])
  ),
  constraint draft_watch_article_candidates_topic_type_check check (
    topic_type = any (array['player_watch', 'scout_meeting', 'game_report', 'ranking', 'other'])
  )
);
```

公開時の流れ:

1. `draft_watch_article_candidates` に下書きを作る。
2. 人間が確認する。
3. 公開する場合、既存の `public.articles` にINSERTする。
4. `draft_watch_article_candidates.status = published` に更新する。

## 選手抽出の方針

スカウトコメント抽出と選手候補抽出は分離する。

理由:

- スカウトコメントがない記事にも有力選手情報はある。
- 「プロ注目」「最速152キロ」「ドラフト上位候補」などの記事から選手候補を拾いたい。
- スカウトコメント抽出結果だけに依存すると、コメントがない選手を登録できない。

推奨フロー:

```text
記事取得
  ↓
記事シグナル判定
  ↓
has_player_candidate=True の記事で選手候補抽出
  ↓
players 既存チェック
  ↓
未登録なら player_candidates に保存
  ↓
has_scout_comment_candidate=True の記事だけスカウトコメント抽出
  ↓
scout_comments に保存
```

選手候補抽出の対象条件:

- `プロ注目`
- `今秋ドラフト`
- `ドラフト候補`
- `上位候補`
- `1位候補`
- `最速150キロ` 以上
- `スカウト視察`
- `12球団`
- `○球団○人`
- `has_attention_candidate=True`
- `has_scout_comment_candidate=True`

## Draft-Watch記事化の方針

Draft-Watch記事化は、外部ニュースをそのままコピーするのではなく、複数情報を整理した独自下書きとして生成する。

記事化候補条件:

- 12球団視察
- 8球団以上視察
- 10人以上のスカウト視察
- MLB視察あり
- 複数球団のスカウトコメントあり
- スカウト会議・編成会議・リストアップ系の記事
- 同じ選手の記事が短期間に複数本出ている
- 注目度スコアが一定以上

スカウト会議記事の検出語:

- `スカウト会議`
- `編成会議`
- `ドラフト会議へ向け`
- `リストアップ`
- `上位候補`
- `1位候補`
- `指名候補`
- `候補選手を確認`
- `球団幹部`

記事生成時は、先に構造化データを作る。

```json
{
  "topic": "立命大・有馬伽久にNPB12球団24人が集結",
  "main_players": ["有馬伽久", "米沢友翔"],
  "attention": {
    "team_count": 12,
    "person_count": 24,
    "teams": ["日本ハム"],
    "notable_notes": ["日本ハムは最多4人態勢", "栗山英樹CBOが視察"]
  },
  "scout_comments": [
    {
      "team": "fighters",
      "scout_name": "栗山CBO",
      "comment": "いい投手であることは間違いない..."
    }
  ],
  "source_urls": []
}
```

その後、Draft-Watch用の下書きを生成する。

## Google Sheetsの扱い

Sheetsは正本ではなく、レビュー用ビューにする。

残す価値があるSheets:

- `Review_PlayerCandidates`
- `Review_DraftWatchCandidates`
- `Review_AttentionHighScore`
- `Review_AIWarnings`

やめる方向のSheets:

- 全記事本文の恒常保存
- URL重複判定の正本利用
- DBに保存済みの全データの単純ミラー

## 移行ステップ

### Phase 1: 記事重複判定をDBへ移す

- `crawled_articles` を作成する。
- `get_existing_urls_by_source()` の代替として、Supabaseから既存URLを取得する。
- 新規記事は `crawled_articles` にupsertする。
- Sheets出力はまだ残す。

実装SQL:

- `database/schema_crawled_articles.sql`

### Phase 2: 選手候補をDBへ保存する

- `extract_player_candidates_with_ai()` を追加する。
- `player_candidates` にupsertする。
- `players` への自動昇格はまだ行わない。

### Phase 3: 注目度シグナルをDBへ保存する

- 現在Sheetsに出している `attention_rows` を `attention_signals` に保存する。
- Draft-Watch記事化判定はこのテーブルを使う。

### Phase 4: Draft-Watch記事候補を作る

- `draft_watch_article_candidates` を作成する。
- 注目度スコア、スカウト会議検出、同一選手クラスタリングから下書きを生成する。
- 公開は手動確認にする。

### Phase 5: Sheetsをレビュー用だけに縮小する

- 全記事出力をやめる。
- 確認が必要な候補だけSheetsに出す。
- 処理自体はSheetsがなくても動くようにする。

## 最初に実装するべき範囲

最初の実装ゴールは次の範囲にする。

1. `crawled_articles` の設計・作成
2. URL重複判定をSheetsからDBへ移行
3. `player_candidates` の設計・作成
4. 選手候補抽出AIの追加
5. 未登録選手を `player_candidates` に保存

Draft-Watch記事化は、その後に `attention_signals` と `draft_watch_article_candidates` を使って実装する。
