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

このテーブルは **記事ごとの抽出結果** ではなく、**選手候補ごとの集約レコード** として扱う。
同じ選手が複数の記事で言及された場合、`player_candidates` は1行のまま維持し、記事ごとの根拠は後述の `player_candidate_sources` に追加する。

用途:

- `players` に未登録の選手を仮登録する。
- AI抽出ミスや表記揺れを人間が確認する。
- 信頼度が高いものだけ `players` に昇格する。
- 昇格時に `players` へコピーしやすい形で、最低限の `players` 互換カラムを持つ。

推奨カラム:

```sql
create table public.player_candidates (
  id uuid primary key default gen_random_uuid(),
  player_id uuid null references public.players(id),
  name text not null,
  name_kana text null,
  team text null,
  team_name text null,
  category text null,
  draft_year integer null,
  school_year text null,
  positions text[] null,
  throws text null,
  bats text null,
  height_cm integer null,
  weight_kg integer null,
  birth_date date null,
  fastball_max integer null,
  description text null,
  source_count integer not null default 0,
  latest_source_url text null,
  latest_source_title text null,
  latest_evidence text null,
  latest_confidence numeric null,
  status text not null default 'pending',
  extracted_raw jsonb null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint player_candidates_status_check check (
    status = any (array['pending', 'approved', 'rejected', 'promoted'])
  ),
  constraint player_candidates_confidence_check check (
    latest_confidence is null or (latest_confidence >= 0 and latest_confidence <= 1)
  )
);
```

推奨index:

```sql
create index idx_player_candidates_name on public.player_candidates (name);
create index idx_player_candidates_team on public.player_candidates (team);
create index idx_player_candidates_category on public.player_candidates (category);
create index idx_player_candidates_draft_year on public.player_candidates (draft_year);
create index idx_player_candidates_status on public.player_candidates (status);
create unique index idx_player_candidates_unique_candidate
  on public.player_candidates (name, coalesce(team, team_name, ''), coalesce(draft_year, 0));
```

運用方針:

- 最初は `players` へ直接INSERTしない。
- `player_candidates.status = pending` として保存する。
- 既存 `players` に同名・表記揺れ一致する選手がいれば `player_candidates` には保存しない。
- 既存 `player_candidates` に同じ `name + team + draft_year` の候補があれば新規候補行は作らず、`player_candidate_sources` だけ追加する。
- `draft_year` をドラフト対象年の正本にする。高校3年、大学4年、社会人の大卒2年目・高卒3年目は記事公開年を入れ、下級生は公開年から逆算する。
- `school_year` はAI抽出根拠・参考情報として残すが、レビューや重複判定では `draft_year` を使う。
- 守備位置は `positions text[]` を正本にする。単数でも配列で保存し、`position text` は持たない。
- 投打は `throws = R/L`, `bats = R/L/S` に正規化して保存する。`S` は両打。
- 人間確認後、または高信頼度条件を満たした場合のみ `players` へ昇格する。

### 3. `player_candidate_sources`

`player_candidates` がどの記事から抽出されたかを保存する。

用途:

- 同じ選手候補に対して複数記事の根拠を蓄積する。
- 候補レビュー時に「どの記事で、どの文から抽出されたか」を確認する。
- 未承認候補・承認済み選手のタイムライン表示の元データにする。

推奨カラム:

```sql
create table public.player_candidate_sources (
  id uuid primary key default gen_random_uuid(),
  player_candidate_id uuid not null references public.player_candidates(id) on delete cascade,
  crawled_article_id uuid null references public.crawled_articles(id),
  source_url text not null,
  source_title text null,
  published_at timestamp with time zone null,
  source text null,
  category text null,
  evidence text null,
  confidence numeric null,
  extracted_raw jsonb null,
  created_at timestamp with time zone not null default now(),
  constraint player_candidate_sources_confidence_check check (
    confidence is null or (confidence >= 0 and confidence <= 1)
  )
);
```

推奨index:

```sql
create index idx_player_candidate_sources_candidate_id
  on public.player_candidate_sources (player_candidate_id);
create index idx_player_candidate_sources_crawled_article_id
  on public.player_candidate_sources (crawled_article_id);
create index idx_player_candidate_sources_source_url
  on public.player_candidate_sources (source_url);
create unique index idx_player_candidate_sources_unique
  on public.player_candidate_sources (player_candidate_id, source_url, coalesce(md5(evidence), ''));
```

### 4. `attention_signals`

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
  player_id uuid null references public.players(id),
  player_candidate_id uuid null references public.player_candidates(id),
  player_name text null,
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

実装メモ:

- 最初は記事単位で保存する。
- 保存済みの `player_article_sources` / `player_candidate_sources` と同じ `source_url` があれば、`player_id` または `player_candidate_id` を自動で埋める。
- `player_candidate_id` が埋まると、未承認候補のレビュー画面でも注目度シグナルをタイムライン表示できる。

### 4.5. `scout_comments` の候補リンク

`scout_comments` はスカウトコメントの正本として維持する。
未登録選手へのスカウトコメントも承認後に正式選手へ引き継げるよう、既存の `player_id` に加えて `player_candidate_id` と `player_name` を持つ。

```sql
alter table public.scout_comments
  add column player_candidate_id uuid null references public.player_candidates(id) on delete set null,
  add column player_name text null;
```

保存ルール:

- 抽出選手が `players` に存在する場合は `player_id` を入れる。
- `players` に存在せず、同じ `source_url` と選手名で `player_candidate_sources` に候補根拠がある場合は `player_candidate_id` を入れる。
- 候補承認時は `scout_comments.player_candidate_id` をキーに `player_id` を更新する。

承認後の反映:

```sql
select public.promote_player_candidate_links(:player_candidate_id, :player_id);
```

### 5. `draft_watch_article_candidates`

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

### 6. `draft_watch_article_candidate_sources`

Draft-Watch記事候補と元記事の多対多を保存する。

`draft_watch_article_candidates.source_urls` は一覧表示や簡易upsert用に残してよいが、正規化された出典管理はこのテーブルで行う。

用途:

- 複数の外部記事から1つのDraft-Watch記事候補を作る。
- どの記事が主要ソースで、どの記事が補助情報かを区別する。
- 下書き生成時の引用元・参照元を追跡する。

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
未登録なら player_candidates を検索
  ↓
同じ候補がなければ player_candidates に作成
  ↓
記事ごとの根拠を player_candidate_sources に保存
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

## 選手候補の承認・昇格

`player_candidates` は `players` の下書きそのものではなく、未承認の選手候補マスタとして扱う。

承認時の基本フロー:

```text
player_candidates.status = pending
  ↓
人間が候補内容を確認・補正
  ↓
players に正式登録
  ↓
player_candidates.player_id に players.id を保存
  ↓
player_candidates.status = promoted に更新
```

承認時に `player_candidates.player_id` を埋めることで、候補時代に `player_candidate_sources` に蓄積された記事根拠は、正式な `players` と間接的に紐付く。

例:

```text
players
  ↑ player_candidates.player_id
player_candidates
  ↓ player_candidate_sources
crawled_articles
```

`article_players` は既存の Draft-Watch公開記事 `articles` と `players` を紐付けるためのテーブルであり、外部ニュース記事 `crawled_articles` のタイムライン用途とは分ける。

使い分け:

- 外部ニュース記事: `player_candidate_sources` / `attention_signals` / `scout_comments`
- Draft-Watch公開記事: `article_players`

## 選手タイムラインの方針

選手ページでは、外部ニュース記事とDraft-Watch内の記事の両方を時系列で見せたい。

ただし、タイムライン専用の実体テーブルを作って全データをコピーするのは避ける。
各情報の正本は既存テーブルに残し、タイムラインは view またはAPI側のUNIONクエリで作る。

理由:

- `scout_comments` はスカウトコメントの正本として既に存在する。未承認候補へのコメントは `player_candidate_id`、承認後は `player_id` でも参照できる。
- `attention_signals` は注目度シグナルの正本として持つ。
- `player_candidate_sources` は記事由来の選手候補根拠の正本として持つ。
- `player_article_sources` は既存 `players` に紐付いた外部記事根拠の正本として持つ。
- Draft-Watch内の記事は既存の `articles` + `article_players` を正本として持つ。
- タイムライン実体テーブルへコピーすると、更新・削除・修正時に二重管理になる。

推奨view:

```sql
create or replace view public.player_timeline_items as
select
  pc.player_id,
  pc.id as player_candidate_id,
  pcs.crawled_article_id,
  pcs.source_url,
  coalesce(pcs.source_title, ca.title) as title,
  coalesce(pcs.published_at, ca.published_at) as published_at,
  coalesce(pcs.source, ca.source) as source,
  coalesce(pcs.category, ca.category) as category,
  'candidate'::text as item_type,
  pcs.evidence as body,
  pcs.confidence as confidence,
  null::integer as score,
  pcs.created_at
from public.player_candidate_sources pcs
join public.player_candidates pc on pc.id = pcs.player_candidate_id
left join public.crawled_articles ca on ca.id = pcs.crawled_article_id

union all

select
  pas.player_id,
  null::uuid as player_candidate_id,
  pas.crawled_article_id,
  pas.source_url,
  coalesce(pas.source_title, ca.title) as title,
  coalesce(pas.published_at, ca.published_at) as published_at,
  coalesce(pas.source, ca.source) as source,
  coalesce(pas.category, ca.category) as category,
  'player_article'::text as item_type,
  pas.evidence as body,
  pas.confidence as confidence,
  null::integer as score,
  pas.created_at
from public.player_article_sources pas
left join public.crawled_articles ca on ca.id = pas.crawled_article_id

union all

select
  sc.player_id,
  sc.player_candidate_id,
  ca.id as crawled_article_id,
  sc.source_url,
  ca.title,
  coalesce(sc.published_at, ca.published_at) as published_at,
  ca.source,
  ca.category,
  'scout_comment'::text as item_type,
  concat_ws(' ', sc.team_name, sc.scout_name, sc.comment) as body,
  null::numeric as confidence,
  null::integer as score,
  sc.created_at
from public.scout_comments sc
left join public.crawled_articles ca on ca.url = sc.source_url
where sc.player_id is not null or sc.player_candidate_id is not null

union all

select
  ats.player_id,
  ats.player_candidate_id,
  ats.crawled_article_id,
  ats.source_url,
  coalesce(ats.source_title, ca.title) as title,
  coalesce(ats.published_at, ca.published_at) as published_at,
  coalesce(ats.source, ca.source) as source,
  coalesce(ats.category, ca.category) as category,
  'attention'::text as item_type,
  ats.evidence as body,
  null::numeric as confidence,
  ats.score,
  ats.created_at
from public.attention_signals ats
left join public.crawled_articles ca on ca.id = ats.crawled_article_id
where ats.player_id is not null or ats.player_candidate_id is not null

union all

select
  ap.player_id,
  null::uuid as player_candidate_id,
  null::uuid as crawled_article_id,
  null::text as source_url,
  a.title,
  a.published_at,
  'Draft-Watch'::text as source,
  a.category,
  'draft_watch_article'::text as item_type,
  coalesce(a.excerpt, a.meta_description) as body,
  null::numeric as confidence,
  null::integer as score,
  ap.created_at
from public.article_players ap
join public.articles a on a.id = ap.article_id
where ap.player_id is not null;
```

正式選手ページでは `player_id` で取得する。

```sql
select *
from public.player_timeline_items
where player_id = :player_id
order by published_at desc nulls last, created_at desc;
```

未承認候補レビュー画面では `player_candidate_id` で取得する。

```sql
select *
from public.player_timeline_items
where player_candidate_id = :player_candidate_id
order by published_at desc nulls last, created_at desc;
```

タイムラインに入れる情報:

- `candidate`: AIが記事から抽出した選手候補根拠
- `player_article`: 既存 `players` に紐付いた外部記事根拠
- `scout_comment`: スカウトコメント
- `attention`: NPB/MLB視察、視察球団数、注目度スコア
- `draft_watch_article`: Draft-Watch公開記事。`articles` + `article_players` 由来。

`scout_comments` はタイムラインテーブルへ移さない。
`scout_comments` はスカウトコメントの正本として維持し、タイムラインでは view で読み出す。

### 既存選手の記事根拠

AI抽出した選手が既に `players` に存在する場合、`player_candidates` には保存しない。
代わりに `player_article_sources` に外部記事根拠を保存する。

```text
players
  ↓
player_article_sources
  ↓
crawled_articles
```

これにより、既存選手についても外部記事タイムラインが蓄積される。

注目度シグナル保存時は、先に `player_article_sources` / `player_candidate_sources` を保存しておく。
その後 `attention_signals` 保存時に同じ `source_url` を探し、`player_id` または `player_candidate_id` を自動補完する。

推奨カラム:

```sql
create table public.player_article_sources (
  id uuid primary key default gen_random_uuid(),
  player_id uuid not null references public.players(id) on delete cascade,
  crawled_article_id uuid null references public.crawled_articles(id),
  source_url text not null,
  source_title text null,
  published_at timestamp with time zone null,
  source text null,
  category text null,
  evidence text null,
  confidence numeric null,
  extracted_raw jsonb null,
  created_at timestamp with time zone not null default now()
);
```

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
- `player_candidates` を候補単位でupsertする。
- 記事ごとの根拠は `player_candidate_sources` に保存する。
- `players` への自動昇格はまだ行わない。

### Phase 3: 注目度シグナルをDBへ保存する

- 現在Sheetsに出している `attention_rows` を `attention_signals` に保存する。
- 同じ `source_url` の選手根拠があれば、`player_id` / `player_candidate_id` を補完する。
- Draft-Watch記事化判定はこのテーブルを使う。

### Phase 4: Draft-Watch記事候補を作る

- `draft_watch_article_candidates` を作成する。
- `draft_watch_article_candidate_sources` を作成する。
- 注目度スコア、スカウト会議検出、同一選手クラスタリングから下書きを生成する。
- 公開は手動確認にする。

### Phase 5: 選手タイムラインを作る

- `player_timeline_items` view を作成する。
- 未承認候補は `player_candidate_id` でタイムラインを確認する。
- 承認済み選手は `player_id` でタイムラインを確認する。
- Draft-Watch公開記事は `articles` + `article_players` をUNIONして追加する。

### Phase 6: Sheetsをレビュー用だけに縮小する

- 全記事出力をやめる。
- 確認が必要な候補だけSheetsに出す。
- 処理自体はSheetsがなくても動くようにする。

## 最初に実装するべき範囲

最初の実装ゴールは次の範囲にする。

1. `crawled_articles` の設計・作成
2. URL重複判定をSheetsからDBへ移行
3. `player_candidates` の設計・作成
4. `player_candidate_sources` の設計・作成
5. 選手候補抽出AIの追加
6. 未登録選手を `player_candidates` に保存
7. 記事ごとの根拠を `player_candidate_sources` に保存

Draft-Watch記事化は、その後に `attention_signals` と `draft_watch_article_candidates` を使って実装する。
選手ページのタイムラインは `player_timeline_items` view を使って実装する。
