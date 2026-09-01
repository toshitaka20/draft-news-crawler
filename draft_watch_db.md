## Table `players`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `name` | `text` |  |
| `name_kana` | `text` |  |
| `position` | `_text` |  |
| `height_cm` | `int4` |  Nullable |
| `weight_kg` | `int4` |  Nullable |
| `team` | `text` |  |
| `category` | `text` |  |
| `fastball_max` | `int4` |  Nullable |
| `breaking_balls` | `_text` |  Nullable |
| `long_throw_m` | `int4` |  Nullable |
| `fifty_m_time` | `numeric` |  Nullable |
| `bio` | `text` |  Nullable |
| `is_featured` | `bool` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |
| `career` | `_text` |  Nullable |
| `throw` | `text` |  Nullable |
| `bat` | `text` |  Nullable |
| `prefecture` | `text` |  Nullable |
| `rank` | `int4` |  Nullable |
| `youtube_urls` | `_text` |  Nullable |
| `draft_year` | `int4` |  |
| `declared` | `bool` |  Nullable |
| `description` | `text` |  Nullable |
| `likes_count` | `int4` |  Nullable |

## Table `stats`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `player_id` | `uuid` |  Nullable |
| `year` | `int4` |  |
| `season` | `text` |  |
| `games` | `int4` |  Nullable |
| `at_bats` | `int4` |  Nullable |
| `hits` | `int4` |  Nullable |
| `home_runs` | `int4` |  Nullable |
| `rbis` | `int4` |  Nullable |
| `steals` | `int4` |  Nullable |
| `avg` | `numeric` |  Nullable |
| `obp` | `numeric` |  Nullable |
| `slg` | `numeric` |  Nullable |
| `ops` | `numeric` |  Nullable |
| `innings` | `numeric` |  Nullable |
| `era` | `numeric` |  Nullable |
| `strikeouts` | `int4` |  Nullable |
| `strikeouts_per_9` | `numeric` |  Nullable |
| `hits_allowed` | `int4` |  Nullable |
| `batting_avg_against` | `numeric` |  Nullable |
| `walks_plus_hit_by_pitch` | `int4` |  Nullable |
| `bbh_per_9` | `numeric` |  Nullable |
| `whip` | `numeric` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `update_at` | `timestamptz` |  Nullable |
| `tournament` | `text` |  Nullable |
| `doubles` | `int4` |  Nullable |
| `triples` | `int4` |  Nullable |
| `walks` | `int4` |  Nullable |
| `hit_by_pitch` | `int4` |  Nullable |
| `sacrifice_flies` | `int4` |  Nullable |
| `batter_strikeouts` | `int4` |  Nullable |
| `period` | `text` |  Nullable |
| `earned_runs` | `int4` |  Nullable |

## Table `scout_comments`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `player_id` | `uuid` |  Nullable |
| `player_candidate_id` | `uuid` | Nullable, references `player_candidates(id)` |
| `player_name` | `text` | Nullable |
| `team_name` | `text` |  |
| `scout_name` | `text` |  |
| `comment` | `text` |  |
| `published_at` | `timestamptz` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `update_at` | `timestamptz` |  Nullable |
| `source_url` | `text` |  Nullable |

## Table `scout_meeting_notes`

球団ごとのスカウト会議・編成方針の報道を、**会議単位のナラティブ**として保存する。

Draft-Watch の `/scouts/[team]/[year]` ページ「スカウト会議・編成方針」セクションの元データ。サイト側はテーブルを直接selectせず、DB関数 `get_team_meeting_notes(p_team_key, p_draft_year)`（SECURITY DEFINER）経由で読む（draft-watchリポ `lib/data.ts` の `getTeamMeetingNotes`）。

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary, default `gen_random_uuid()` |
| `team_key` | `text` | NOT NULL。`fighters` / `carp` / `tigers` などの球団キー |
| `draft_year` | `int4` | NOT NULL |
| `meeting_date` | `date` | Nullable（会議日が特定できない報道では空） |
| `article_date` | `date` | Nullable。報道日 |
| `content` | `text` | NOT NULL。会議内容の要約（絞り込み人数・補強方針・挙がった選手名など） |
| `source_name` | `text` | Nullable。媒体名（例: 日刊スポーツ、スポニチ、道新スポーツ） |
| `source_url` | `text` | Nullable |
| `confidence` | `text` | Nullable。実データで使われている値は `high` / `medium` |
| `created_at` | `timestamptz` | default `now()` |

### Notes

- 同一の会議を複数媒体が報じた場合は媒体ごとに1行入れてよい（日本ハムの2026-02-12は道新スポーツとデイリースポーツで2行ある）。
- サイト表示は `meeting_date`（無ければ `article_date`）の降順。
- CHECK制約の有無は未確認。上記の値はいずれも実データで観測されたもの。

## Table `scout_meeting_mentions`

スカウト会議で名前が挙がった**選手単位**の言及を保存する。`scout_meeting_notes` が「会議そのもの」、こちらが「その会議で誰の名前が挙がったか」という分担。

`/scouts/[team]/[year]` ページの「注目選手リストアップ」で、DB関数 `get_team_listup(p_team_key, p_draft_year)` 経由で視察・スカウトコメントと選手単位に名寄せされ、会議バッジと `meeting_note` として表示される（draft-watchリポ `lib/data.ts` の `getTeamListup`）。

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary, default `gen_random_uuid()` |
| `team_key` | `text` | NOT NULL |
| `draft_year` | `int4` | NOT NULL |
| `player_id` | `uuid` | NOT NULL, references `players(id)` |
| `player_name` | `text` | Nullable。表示・照合用の冗長カラム |
| `meeting_date` | `date` | Nullable |
| `article_date` | `date` | Nullable |
| `mention_type` | `text` | Nullable。実データの値は下記参照 |
| `note` | `text` | Nullable。その会議でどう言及されたかの説明文 |
| `confidence` | `text` | Nullable。実データで使われている値は `high` / `medium` / `low` |
| `source_name` | `text` | Nullable |
| `source_url` | `text` | Nullable |
| `created_at` | `timestamptz` | default `now()` |

### mention_type の値（実データで観測されるもの）

| 値 | 意味 |
|---|---|
| `scout_meeting_listed` | 会議で指名候補としてリストアップされた／名前が挙がった |
| `scout_meeting_checked` | 会議で映像確認・評価の確認対象になった |
| `reported_listed` | 会議の場ではないが、報道でその球団のリストアップとして名前が挙がった |

### Notes

- `player_id` が NOT NULL なので、`players` に存在しない選手は登録できない。先に選手を作るか `player_candidates` から昇格させる必要がある。
- `player_name` は実データではスペース無し表記（例: `織田翔希`）。`players.name` はスペース有り（`織田 翔希`）なので、この列での突き合わせはしないこと。
- 「1位候補に含まれているとみられる」のような推量報道は `confidence='medium'` とし、`note` に推定である旨を明記する運用。
- CHECK制約の有無は未確認。上記の値はいずれも実データで観測されたもの。

## Table `articles`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `title` | `text` |  |
| `slug` | `text` |  Unique |
| `excerpt` | `text` |  Nullable |
| `content` | `text` |  Nullable |
| `thumbnail_url` | `text` |  Nullable |
| `meta_title` | `text` |  Nullable |
| `meta_description` | `text` |  Nullable |
| `is_published` | `bool` |  Nullable |
| `published_at` | `timestamptz` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |
| `type` | `text` |  |
| `category` | `text` |  |
| `teams` | `_text` |  Nullable |
| `draft_year` | `int4` |  Nullable |
| `likes_count` | `int4` |  Nullable |

## Table `article_players`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `article_id` | `uuid` |  Nullable |
| `player_id` | `uuid` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `draft_predictions`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `team_key` | `text` |  |
| `year` | `int4` |  |
| `round_category` | `text` |  |
| `player_id` | `uuid` |  |
| `sort_order` | `int4` |  |
| `note` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |

## Table `scouts`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `team_name` | `text` |  |
| `name` | `text` |  |
| `position` | `text` |  Nullable |
| `area` | `text` |  Nullable |
| `main_players` | `_text` |  Nullable |
| `note` | `text` |  Nullable |
| `career` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |
| `sort_order` | `int4` |  Nullable |

## Table `drafted_players`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary |
| `year` | `int4` |  |
| `team_key` | `varchar` |  |
| `rank` | `varchar` |  |
| `name` | `varchar` |  |
| `team` | `varchar` |  |
| `position` | `varchar` |  |
| `contract_type` | `varchar` |  |
| `category` | `varchar` |  |
| `note` | `text` |  Nullable |
| `created_at` | `timestamp` |  Nullable |
| `updated_at` | `timestamp` |  Nullable |

## Table `draft_first_bids`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `year` | `int4` |  |
| `team_key` | `varchar` |  |
| `bid_order` | `int4` |  |
| `player_name` | `varchar` |  |
| `position` | `varchar` |  Nullable |
| `category` | `varchar` |  Nullable |
| `result` | `bool` |  |
| `is_competition` | `bool` |  Nullable |
| `created_at` | `timestamp` |  Nullable |
| `updated_at` | `timestamp` |  Nullable |

## Table `player_achievements`

選手の実績・経歴（侍ジャパン選抜歴、全国大会出場歴、タイトル歴）

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `player_id` | `uuid` |  |
| `type` | `text` |  |
| `year` | `int4` |  |
| `tournament_name` | `text` |  |
| `result` | `text` |  |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |

## Table `comments`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `article_id` | `uuid` |  Nullable |
| `player_id` | `uuid` |  Nullable |
| `author_name` | `text` |  |
| `author_email` | `text` |  Nullable |
| `content` | `text` |  |
| `is_approved` | `bool` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |

## Table `likes`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `article_id` | `uuid` |  Nullable |
| `player_id` | `uuid` |  Nullable |
| `user_identifier` | `text` |  |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |

## Table `contact_inquiries`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `name` | `text` |  |
| `email` | `text` |  |
| `subject` | `text` |  |
| `message` | `text` |  |
| `status` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |

## Table `draft_lists`

ドラフト予想（1位12人、12球団1位入札、各球団指名）

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `user_id` | `uuid` |  |
| `year` | `int4` |  |
| `type` | `text` |  |
| `user_name` | `text` |  |
| `likes_count` | `int4` |  |
| `data` | `jsonb` |  |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |

## Table `user_profiles`

ユーザープロフィール（ニックネーム、推しチーム、推し選手など）

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `user_id` | `uuid` | Primary |
| `nickname` | `text` |  Nullable |
| `favorite_team` | `text` |  Nullable |
| `bio` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |
| `favorite_player_ids` | `jsonb` |  Nullable |

## Table `draft_list_comments`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `draft_list_id` | `uuid` |  |
| `author_name` | `text` |  |
| `author_email` | `text` |  Nullable |
| `content` | `text` |  |
| `is_approved` | `bool` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |

## Table `player_rank_predictions`

ログインユーザーによる「この選手は何位で指名されるか」の投票（選手×ユーザーで1票）。crawlerは書かない、サイト側で生成されるユーザーデータ。

`/players/[year]/[id]` の順位予想、`/my-draft-list/rank`、マイページで読み書きする。集計はDB関数 `get_player_rank_summary` / `get_player_rank_leaderboard` / `get_overall_player_ranking` 経由。トップページの「急上昇」ランキングだけは `created_at` で期間を切って直接selectしている（draft-watchリポ `lib/data.ts` の `getTrendingPlayerRanking`）。

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary, default `gen_random_uuid()` |
| `player_id` | `uuid` | NOT NULL, references `players(id)` |
| `user_id` | `uuid` | NOT NULL。`auth.users` のユーザー |
| `bucket` | `text` | NOT NULL。9区分（下記） |
| `created_at` | `timestamptz` | default `now()` |
| `updated_at` | `timestamptz` | default `now()` |

### bucket の値

上位指名ほど weight が大きい9区分。定義の正本は draft-watchリポの `lib/draft-rank.ts`（`RANK_BUCKETS`）。

| 値 | ラベル | weight |
|---|---|---|
| `kyogo` | 競合（1位重複） | 9 |
| `tandoku` | 単独1位 | 8 |
| `hazure1` | 外れ1位 | 7 |
| `r2` | 2位 | 6 |
| `r3` | 3位 | 5 |
| `r4` | 4位 | 4 |
| `r5` | 5位 | 3 |
| `r6plus` | 6位〜 | 2 |
| `ikusei` | 育成 | 1 |

## Table `crawled_articles`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `source` | `text` |  |
| `category` | `text` |  Nullable |
| `url` | `text` |  Unique |
| `title` | `text` |  |
| `body` | `text` |  Nullable |
| `published_at` | `timestamptz` |  Nullable |
| `has_scout_comment_candidate` | `bool` |  |
| `has_attention_candidate` | `bool` |  |
| `has_player_candidate` | `bool` |  |
| `content_hash` | `text` |  Nullable |
| `raw` | `jsonb` |  Nullable |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

## Missing Tables for Data Pipeline

`docs/data_pipeline_strategy.md` の実装に対して、現行DBで不足しているテーブル。

SQL: `database/schema_data_pipeline_phase2_4.sql`

### Table `player_candidates`

記事から抽出した選手候補を、`players` に直接入れる前のレビュー用として保存する。

`players` は既に存在するため、未確定データやAI抽出結果をここに隔離する。
このテーブルは記事ごとの行ではなく、選手候補ごとに集約する。記事ごとの根拠は `player_candidate_sources` に保存する。

#### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `crawled_article_id` | `uuid` | Nullable, references `crawled_articles(id)` |
| `player_id` | `uuid` | Nullable, references `players(id)` |
| `name` | `text` |  |
| `name_kana` | `text` | Nullable |
| `team` | `text` | Nullable |
| `team_name` | `text` | Nullable |
| `category` | `text` | Nullable |
| `draft_year` | `int4` | Nullable |
| `school_year` | `text` | Nullable |
| `positions` | `_text` | Nullable |
| `throws` | `text` | Nullable |
| `bats` | `text` | Nullable |
| `height_cm` | `int4` | Nullable |
| `weight_kg` | `int4` | Nullable |
| `birth_date` | `date` | Nullable |
| `fastball_max` | `int4` | Nullable |
| `description` | `text` | Nullable |
| `source_count` | `int4` | default `0` |
| `latest_source_url` | `text` | Nullable |
| `latest_source_title` | `text` | Nullable |
| `latest_evidence` | `text` | Nullable |
| `latest_confidence` | `numeric` | Nullable, 0-1 |
| `status` | `text` | default `pending` |
| `extracted_raw` | `jsonb` | Nullable |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

#### Constraints / Indexes

- `status in ('pending', 'approved', 'rejected', 'promoted')`
- `latest_confidence is null or latest_confidence between 0 and 1`
- unique: `(name, coalesce(team, team_name, ''), coalesce(draft_year, 0))`
- index: `crawled_article_id`, `player_id`, `name`, `team`, `category`, `draft_year`, `status`, `created_at`

### Table `player_candidate_sources`

選手候補がどの記事から抽出されたかを保存する。

同一選手候補が複数記事で言及された場合、`player_candidates` は1行のまま、この記事根拠テーブルに行が追加される。

#### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `player_candidate_id` | `uuid` | references `player_candidates(id)` |
| `crawled_article_id` | `uuid` | Nullable, references `crawled_articles(id)` |
| `source_url` | `text` |  |
| `source_title` | `text` | Nullable |
| `published_at` | `timestamptz` | Nullable |
| `source` | `text` | Nullable |
| `category` | `text` | Nullable |
| `evidence` | `text` | Nullable |
| `confidence` | `numeric` | Nullable, 0-1 |
| `extracted_raw` | `jsonb` | Nullable |
| `created_at` | `timestamptz` |  |

#### Constraints / Indexes

- `confidence is null or confidence between 0 and 1`
- unique: `(player_candidate_id, source_url, coalesce(md5(evidence), ''))`
- index: `player_candidate_id`, `crawled_article_id`, `source_url`, `published_at`

### Table `attention_signals`

視察球団数、視察人数、球団名、MLB視察有無、注目度スコアを保存する。

現行の `AttentionSignals` Sheet 相当のDB正本。Sheetには選手列がないが、DBでは選手別の注目度集計に使えるよう `player_id/player_name/player_candidate_id` を nullable で持つ。

#### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `crawled_article_id` | `uuid` | Nullable, references `crawled_articles(id)` |
| `player_id` | `uuid` | Nullable, references `players(id)` |
| `player_candidate_id` | `uuid` | Nullable, references `player_candidates(id)` |
| `player_name` | `text` | Nullable |
| `source_url` | `text` |  |
| `source_title` | `text` | Nullable |
| `published_at` | `timestamptz` | Nullable |
| `source` | `text` | Nullable |
| `category` | `text` | Nullable |
| `team_count` | `int4` | default `0` |
| `person_count` | `int4` | default `0` |
| `teams` | `_text` | default empty array |
| `has_npb` | `bool` | default `false` |
| `has_mlb` | `bool` | default `false` |
| `score` | `int4` | default `0` |
| `evidence` | `text` |  |
| `evidence_hash` | `text` | generated from `md5(evidence)` |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

#### Constraints / Indexes

- `team_count >= 0`
- `person_count >= 0`
- `score >= 0`
- unique: `(source_url, evidence_hash)`
- index: `crawled_article_id`, `player_id`, `player_candidate_id`, `player_name`, `source_url`, `published_at`, `score desc`, `has_mlb`
- GIN index: `teams`

### Table `draft_watch_article_candidates`

Draft-Watchで記事化する候補・下書きを保存する。

公開記事本体は既存の `articles` に作る。ここでは「記事化候補」「生成下書き」「公開済み記事との対応」を管理する。

#### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `topic_key` | `text` | Nullable, Unique when present |
| `topic_type` | `text` |  |
| `main_player_id` | `uuid` | Nullable, references `players(id)` |
| `main_player_name` | `text` | Nullable |
| `title` | `text` |  |
| `importance_score` | `int4` | default `0` |
| `source_urls` | `_text` | default empty array |
| `summary_json` | `jsonb` | Nullable |
| `draft_article_markdown` | `text` | Nullable |
| `published_article_id` | `uuid` | Nullable, references `articles(id)` |
| `review_note` | `text` | Nullable |
| `status` | `text` | default `draft` |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

#### Constraints / Indexes

- `status in ('draft', 'reviewed', 'published', 'rejected')`
- `topic_type in ('player_watch', 'scout_meeting', 'game_report', 'ranking', 'other')`
- `importance_score >= 0`
- unique: `topic_key where topic_key is not null`
- index: `status`, `topic_type`, `importance_score desc`, `main_player_id`, `published_article_id`, `created_at`
- GIN index: `source_urls`

### Table `draft_watch_article_candidate_sources`

Draft-Watch記事候補と元記事の多対多を保存する。

`draft_watch_article_candidates.source_urls` は一覧表示や簡易upsert用に残し、正規化された出典管理はこのテーブルで行う。

#### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `draft_watch_article_candidate_id` | `uuid` | references `draft_watch_article_candidates(id)` |
| `crawled_article_id` | `uuid` | Nullable, references `crawled_articles(id)` |
| `source_url` | `text` |  |
| `role` | `text` | default `source` |
| `created_at` | `timestamptz` |  |

#### Constraints / Indexes

- `role in ('primary', 'source', 'supporting')`
- unique: `(draft_watch_article_candidate_id, source_url)`
- index: `draft_watch_article_candidate_id`, `crawled_article_id`, `source_url`

### Table `scout_visits`

**個別の視察イベント**を1行1件で保存する。「いつ・どの球団が・誰を見に来たか」の正本。

`attention_signals` との違い: `attention_signals` は記事単位の集計（視察球団数・人数・スコア）、`scout_visits` は球団を1行に分解した明細。球団別の視察タイムラインや選手別の視察サマリはこちらから作る。

サイト側はテーブルを直接selectせず、DB関数 `get_player_visit_summary` / `get_player_scout_visits` / `get_team_visit_timeline` / `get_team_listup`（いずれもSECURITY DEFINER）経由で読む。

#### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary, default `gen_random_uuid()` |
| `crawled_article_id` | `uuid` | Nullable, references `crawled_articles(id)` |
| `player_id` | `uuid` | Nullable, references `players(id)` |
| `player_candidate_id` | `uuid` | Nullable, references `player_candidates(id)` |
| `player_name` | `text` | Nullable |
| `team_key` | `text` | Nullable。視察した球団（12球団キー） |
| `person_count` | `int4` | Nullable。その球団が送り込んだ人数 |
| `event_date` | `date` | Nullable。視察日 |
| `event_date_text` | `text` | Nullable。本文中の日付表現をそのまま（「29日」など） |
| `event_date_precision` | `text` | Nullable。`exact` / `approximate` / `unknown` |
| `source_url` | `text` | Nullable |
| `source_title` | `text` | Nullable |
| `published_at` | `timestamptz` | Nullable |
| `source` | `text` | Nullable。媒体名 |
| `category` | `text` | Nullable。`高校野球` / `大学野球` / `社会人野球` / `大学・社会人野球` |
| `evidence` | `text` | NOT NULL。根拠となる本文抜粋 |
| `evidence_hash` | `text` | Nullable |
| `created_at` | `timestamptz` | default `now()` |
| `updated_at` | `timestamptz` | default `now()` |

#### Notes

- `player_id` / `player_candidate_id` はどちらもNullable。`players` 未登録の選手は `player_candidate_id` 側で受ける。
- `team_key` がNULLの行がある（球団を特定できなかった視察）。球団別集計では落ちる。
- `event_date` はNULLが多数。日付が取れない場合は `published_at` で代用する前提。

### Table `player_article_sources`

選手と記事の多対多を、抽出根拠つきで保存する。`crawled_articles` から選手を抽出した際の出所を残すためのテーブル。

#### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary, default `gen_random_uuid()` |
| `player_id` | `uuid` | NOT NULL, references `players(id)` |
| `crawled_article_id` | `uuid` | Nullable, references `crawled_articles(id)` |
| `source_url` | `text` | NOT NULL |
| `source_title` | `text` | Nullable |
| `published_at` | `timestamptz` | Nullable |
| `source` | `text` | Nullable |
| `category` | `text` | Nullable |
| `evidence` | `text` | Nullable。選手名を含む本文抜粋 |
| `confidence` | `numeric` | Nullable。0〜1 |
| `extracted_raw` | `jsonb` | Nullable。抽出時のLLM出力そのまま（name/team_name/position/throws/bats など） |
| `created_at` | `timestamptz` | default `now()` |

### View `player_timeline_items`

選手ページの「関連ニュース」タイムライン用のビュー。実テーブルではないので直接INSERTしない。

選手に関係する5系統の出来事を `item_type` で束ねた union。サイト側はDB関数 `get_player_news_timeline(p_player_id, p_limit, p_offset)` 経由で読む（draft-watchリポ `lib/data.ts` の `getPlayerNews`）。

| `item_type` | 元テーブル | 件数（2026-09-01時点） |
|---|---|---|
| `scout_comment` | `scout_comments` | 3,447 |
| `player_article` | `player_article_sources` | 3,047 |
| `draft_watch_article` | `articles`（Draft-Watch自前記事。`source` が `Draft-Watch`） | 965 |
| `candidate` | `player_candidate_sources` | 818 |
| `attention` | `attention_signals`（`score` が入るのはこの型のみ） | 632 |

元テーブルの全行が出るわけではない（`player_article_sources` は4,944行あるがビューでは3,047行）。選手に紐付かない行の除外や重複排除が入っているとみられるが、ビュー定義は未確認。

#### Columns

| Name | Type |
|------|------|
| `player_id` | `uuid` |
| `player_candidate_id` | `uuid` |
| `crawled_article_id` | `uuid` |
| `source_url` | `text` |
| `title` | `text`（`scout_comment` ではNULL） |
| `published_at` | `timestamptz` |
| `source` | `text` |
| `category` | `text` |
| `item_type` | `text`（上記5値） |
| `body` | `text`（本文抜粋。`scout_comment` では「球団キー スカウト名 コメント」形式） |
| `confidence` | `numeric` |
| `score` | `int4` |
| `created_at` | `timestamptz` |

## Views

記事の件数カウント用の集計ビュー。いずれも読み取り専用で、サイト側から直接selectしている（draft-watchリポ `lib/data.ts` の `getNewsCategoryCountsFromView` / `getTeamNewsCountsFromView`）。

### View `news_category_counts`

| Name | Type | 備考 |
|------|------|------|
| `category` | `text` | `high_school` / `university` / `social_independent_farm` |
| `count` | `int8` | 該当カテゴリの記事数 |

### View `team_news_counts`

| Name | Type | 備考 |
|------|------|------|
| `team` | `text` | 12球団キー（`tigers` / `eagles` など） |
| `count` | `int8` | 該当球団の記事数 |
