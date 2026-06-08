# Phase 6: 選択候補のリサーチ付き昇格 — 詳細設計

`docs/data_pipeline_strategy.md` の Phase 6 を詳細化した設計書。
管理画面で選択した `player_candidates` を、外部サイトのリサーチで肉付けし、
成績（`stats`）・実績（`player_achievements`）まで揃えたうえで `players` へ昇格する仕組みを定義する。

---

## 1. 目的とスコープ

- 任意のタイミングで、管理画面から任意の選手候補を選んでリサーチ＆昇格できるようにする。
- リサーチで `description` を厚くしつつ、`stats`（年度別成績）と `player_achievements`（実績）も合わせて取得する。
- リサーチ結果は `player_candidates` に保存し、管理画面で確認・修正してから昇格する。
- 昇格時に `players` / `stats` / `player_achievements` を作成し、`promote_player_candidate_links()` でリンクを伝播する。

スコープ外: 管理画面（UI）の実装そのものは別リポ `draft-watch` の管轄。本設計はこのリポ（`draft-news-crawler`）が担うエンジン部分と、両リポの結合方式を定義する。

---

## 2. アーキテクチャ（リポジトリの住み分け）

`draft-watch` は **Next.js + OpenNext + Cloudflare Workers**（Supabase利用、AI/スクレイピング資産なし、CPU/実行時間制限あり）。
重いスクレイピング＋LLM処理は Cloudflare Workers と相性が悪いため、**重い処理はこのPythonリポ**が担い、**画面と起動トリガは `draft-watch`** が担う。両者は **Supabase を結合点**に疎結合する。

```
[draft-watch / Cloudflare Workers]  ── 管理画面・トリガ専任
  app/admin の「リサーチ実行 / 昇格」ボタン
  → app/api/admin/* （軽いI/Oのみ）
  → GitHub REST: workflow_dispatch を fetch で起動（候補IDを inputs で渡す）
        │  ※ Workers→GitHub の fetch は数十msの軽処理。CPU制限に当たらない
        ▼
[draft-news-crawler / GitHub Actions]  ── 重い処理専任（最大6時間 / 無料枠は実行分のみ）
  main_promote.py
    --mode research : 4サイトをリサーチ → Gemini構造化 → マージ → Supabaseへ提案保存
    --mode commit   : 確定データで players/stats/player_achievements を作成 → 昇格
        ▼
[Supabase]  ── 結合点
  player_candidates.research_* 列 / research_status
        ▼
[draft-watch]  ready を表示・修正 → 「昇格」ボタン → commit を workflow_dispatch
```

### コスト前提
- GitHub REST API（`workflow_dispatch` 呼び出し）・PAT/GitHub App は**無料**。レート 5,000回/時（PAT）で管理画面操作には十分。
- 課金対象は起動された Actions の実行分のみ（プライベートで月2,000分の無料枠。実行した分だけ消費）。
- トークンは `draft-watch` 側の Secret に置く。Fine-grained PAT を本リポの `Actions: write` だけに絞る。

---

## 3. リサーチ情報源（4サイト）

選手名＋チーム名で引く。サイトごとに守備範囲が異なるため、**フィールド単位のソース優先度マージ**を前提にする。

| サイト | 強み（取得項目） | 検索/取得 | 備考 |
|---|---|---|---|
| 一球速報.com (`baseball.omyutech.com`) | **年度別の数値成績**（打率/防御率/本塁打/奪三振/四死球…）、出身校 | 検索フォーム＋`playerTop.action?playerId=` | `stats` の一次ソース |
| `player.draft-kaigi.jp` | 球速/50m走/遠投/二塁送球、ランク評価(S〜E)、ドラフト予想順位、進路 | `/SearchPlayer.php` | 身体能力・評価に強い |
| `draft-repo.com` | 身長体重/球速/球種/出身校/簡易プロフィール | ブログ型・カテゴリ絞り込み | 年度別成績は弱い |
| 球歴.com (`kyureki.com`) | 総合（経歴・成績の網羅性） | — | **403対策必須**（UA等） |

### フィールド別マージ優先度
- 数値成績(`stats`): 一球速報 > 球歴 > draft-repo
- 球速/球種/50m/遠投/身体: draft-kaigi > 球歴 > draft-repo > 一球速報
- `declared`（ドラフト志望届）: draft-kaigi > draft-repo
- `rank`（評価ランク）: **リサーチ対象外**。運営が手動設定するため、昇格時は **0 固定**（列は持つが埋めない）
- 経歴・出身校(`career`/`prefecture`): 球歴 > 一球速報 > draft-kaigi
- `description` 素材: **DB内の関連記事（紐づく `crawled_articles` 本文 / `scout_comments` / `attention_signals` の evidence）を主役に、リサーチで集めたWeb記事・プロフィールも活用して充実させてよい**（素材サイトは限定しない）。ただし外部記事の文章をそのまま転載・言い換えせず独自に整理する。数値・評価の単純羅列にせず読み物にする。使った情報の出典は `sources` に残す
- `bio`（経歴文）素材: `career`/`prefecture`/出身校などの事実情報を統合

各採用値には出典（サイト名・URL）を `research_sources` に必ず残す。

---

## 4. スキーマ差分（`player_candidates` を `players` ミラーに拡張）

`players` と項目を揃え、昇格時のマッピングを 1対1 にする。`stats`/`player_achievements` は 1対多のため、提案段階では jsonb 列で保持し、昇格時に各テーブルへ展開する。

```sql
-- database/schema_phase6_player_candidates_promotion.sql

-- 4-1. players に合わせて追加する列（リサーチ値の格納先）
alter table public.player_candidates
  add column if not exists breaking_balls text[],      -- 球種
  add column if not exists long_throw_m   int4,        -- 遠投(m)
  add column if not exists fifty_m_time   numeric,     -- 50m走(秒)
  add column if not exists career         text[],      -- 経歴
  add column if not exists bio            text,        -- 経歴文（descriptionとは別枠）
  add column if not exists prefecture     text,        -- 出身都道府県
  add column if not exists rank           int4,        -- 評価ランク（運営が手動設定。リサーチでは埋めず昇格時は0）
  add column if not exists youtube_urls   text[],      -- 動画URL
  add column if not exists declared       bool;        -- ドラフト志望届の有無

-- 4-2. リサーチ管理列
alter table public.player_candidates
  add column if not exists research_status       text not null default 'none',
  add column if not exists researched_at         timestamptz,
  add column if not exists research_sources       jsonb,  -- フィールド別の出典 {field:{value,provider,url}}
  add column if not exists research_stats         jsonb,  -- stats提案（配列）
  add column if not exists research_achievements  jsonb,  -- achievements提案（配列）
  add column if not exists research_raw           jsonb;  -- 4サイトの生構造化結果（再マージ・検証用）

alter table public.player_candidates
  add constraint player_candidates_research_status_check
  check (research_status in ('none','queued','researching','ready','committed','failed'));

create index if not exists idx_player_candidates_research_status
  on public.player_candidates (research_status);
```

### 名前違いの吸収（昇格時マッピング）
candidate 側の列名は維持し、`players` への INSERT 時に対応付ける。

| player_candidates | players |
|---|---|
| `positions` (`_text`) | `position` (`_text`) |
| `throws` (`text`) | `throw` (`text`) |
| `bats` (`text`) | `bat` (`text`) |
| `name_kana`/`team`/`category`/`draft_year`/`height_cm`/`weight_kg`/`fastball_max`/`description` | 同名 |
| `breaking_balls`/`long_throw_m`/`fifty_m_time`/`career`/`bio`/`prefecture`/`rank`/`youtube_urls`/`declared` | 同名 |
| `birth_date` | （playersに無い→使わない。年齢推定の参考のみ） |

### jsonb の形
```jsonc
// research_stats（昇格時に stats テーブルへ展開）
[
  { "year": 2025, "season": "春", "tournament": "全日本大学選手権", "period": "リーグ戦",
    "games": 12, "innings": 80.1, "era": 1.45, "strikeouts": 95, "whip": 0.98,
    "source_url": "https://baseball.omyutech.com/...", "provider": "ikkyu" }
]
// research_achievements（昇格時に player_achievements へ展開）
[
  { "type": "全国大会", "year": 2024, "tournament_name": "明治神宮大会", "result": "ベスト4",
    "source_url": "https://...", "provider": "draft_kaigi" }
]
// research_sources（採用値ごとの出典）
{ "fastball_max": {"value":151,"provider":"draft_kaigi","url":"https://..."},
  "era_2025":    {"value":1.45,"provider":"ikkyu","url":"https://..."} }
```

---

## 5. モジュール構成

```
research/
  __init__.py
  base.py            # ResearchProvider 抽象 / ResearchDocument
  ikkyu.py           # 一球速報（成績）
  draft_kaigi.py     # player.draft-kaigi.jp（評価・身体能力）
  draft_repo.py      # draft-repo（簡易プロフィール）
  kyureki.py         # 球歴（403対策込み）
  merge.py           # フィールド別ソース優先度マージ＋出典構築
ai/gemini.py         # +structure_player_research_with_gemini / +generate_player_description_with_gemini
database/supabase_client.py  # +SupabasePlayerPromotionStore（提案保存・昇格実行）
main_promote.py      # CLIエントリ（--mode research|commit, --candidate-ids）
.github/workflows/player-promotion.yml  # workflow_dispatch（inputs: mode, candidate_ids）
```

### 5-1. `research/base.py`
```python
@dataclass
class ResearchDocument:
    provider: str          # 'ikkyu' / 'draft_kaigi' / 'draft_repo' / 'kyureki'
    source_url: str
    raw_text: str          # 本文をmarkdown/plaintext化したもの
    fetched_at: str        # ISO8601

class ResearchProvider(ABC):
    name: str
    base_url: str
    # 選手名＋チーム名（＋ドラフト年）で候補ページURLを返す
    def search(self, name: str, team: Optional[str], draft_year: Optional[int]) -> List[str]: ...
    # 候補ページのHTMLを取得し本文化する
    def fetch_profile(self, url: str) -> Optional[ResearchDocument]: ...
    # search→fetch を束ねて返す（同名ヒット時は最大N件）
    def research(self, name, team, draft_year) -> List[ResearchDocument]: ...
```
- 共通の `requests` セッション（`User-Agent`/`Accept-Language` 付与、リトライ、`SLEEP_SECONDS`）は base に集約。
- `kyureki.py` は 403 対策ヘッダを上書き。失敗時は空リストを返してスキップ（他サイトで継続）。

### 5-2. `ai/gemini.py` 追加
```python
def setup_gemini(model_override: Optional[str] = None):
    # 既存を拡張。model_override で flash/pro を切替可能にする

def structure_player_research_with_gemini(
    candidate: Dict[str, Any],
    documents: List[ResearchDocument],
) -> Optional[Dict[str, Any]]:
    """
    プロバイダごとの本文をまとめて渡し、サイト別に構造化JSONを返す。
    出力: { "per_provider": [ {provider, profile:{...}, stats:[...], achievements:[...]} ] }
    数値は出典(provider/url)付き。データに無い項目は創作しない。
    profile に rank は含めない（運営が手動設定するため）。
    モデル: gemini-2.5-flash（数値抽出の正確性優先）
    """

def generate_player_description_with_gemini(
    merged: Dict[str, Any],
    related_articles: List[Dict[str, Any]],    # DB内: 紐づく crawled_articles 本文 / scout_comments / attention_signals
    research_documents: List[Dict[str, Any]],  # リサーチで集めたWeb記事・プロフィール（draft-repo等）
) -> Optional[Dict[str, str]]:
    """
    description は DB内の関連記事を主役に、リサーチで集めたWeb記事・プロフィールも活用して
    充実した紹介文を生成する（素材サイトは限定しない）。
    ただし外部記事の文章をそのまま転載・言い換えせず独自に整理する。数値・評価の単純羅列にしない。
    bio は career/prefecture/出身校などの事実情報から生成。
    出力: {"description": "...", "bio": "..."}
    モデル: gemini-2.5-flash（必要なら model_override で pro）
    """
```

### 5-3. `research/merge.py`
```python
FIELD_PRIORITY: Dict[str, List[str]] = {...}  # field -> provider順

def merge_structured_results(per_provider: List[Dict]) -> Dict[str, Any]:
    """
    フィールド別優先度で profile をマージ、stats/achievements を統合（年度・大会で重複排除）。
    返り値: {profile:{...}, stats:[...], achievements:[...], sources:{field:{value,provider,url}}}
    """
```

### 5-4. `database/supabase_client.py` 追加
```python
class SupabasePlayerPromotionStore:
    def fetch_candidates(self, candidate_ids: List[str]) -> List[Dict]: ...

    def fetch_related_articles(self, candidate_id: str) -> List[Dict]:
        # description素材。player_candidate_sources→crawled_articles.body、
        # および紐づく scout_comments / attention_signals の evidence を集約して返す

    def save_research_result(self, candidate_id: str, merged: Dict) -> None:
        # players ミラー列（profile）＋ research_stats/achievements/sources/raw を更新
        # research_status='ready', researched_at=now()

    def commit_promotion(self, candidate_id: str) -> Optional[str]:
        # 1) candidate のミラー列 → players へ INSERT（列名マッピング適用。rank は 0 固定）→ player_id 取得
        # 2) research_stats → stats へ INSERT（player_id 付与、source は extracted_raw に保持）
        # 3) research_achievements → player_achievements へ INSERT（player_id 付与）
        # 4) RPC promote_player_candidate_links(candidate_id, player_id)
        #    （関数が player_candidates.status='promoted' に更新＋scout_comments/attention_signals/scout_visits を伝播）
        # 5) research_status='committed'
        # 戻り値: player_id

# top-level
def research_player_candidates(candidate_ids: List[str], dummy_mode=False) -> Dict[str, int]: ...
def commit_player_promotions(candidate_ids: List[str], dummy_mode=False) -> Dict[str, int]: ...
```

### 5-5. `main_promote.py`
```bash
python main_promote.py --mode research --candidate-ids "id1,id2,id3"
python main_promote.py --mode commit   --candidate-ids "id1,id2"
```
- `--mode research`: 各候補について全プロバイダをリサーチ → 構造化 → マージ → `save_research_result`
- `--mode commit`: 各候補について `commit_promotion`
- 候補IDは `--candidate-ids`（カンマ区切り）。未指定時は環境変数 `CANDIDATE_IDS` をフォールバック。

---

## 6. 起動フローとステータス遷移

```
research_status:
  none ──(画面: queue化 & research dispatch)──▶ queued ──(worker開始)──▶ researching
       ──(リサーチ成功)──▶ ready ──(画面: 確認・修正 & commit dispatch)──▶ committed
       ──(失敗)──▶ failed（再実行で queued に戻せる）
```

### research（肉付け）
1. 管理画面で候補を複数選択 → 「リサーチ実行」
2. `draft-watch` の admin API が対象候補の `research_status='queued'` に更新し、`workflow_dispatch`（mode=research, candidate_ids）を発火
3. Actions が `main_promote.py --mode research` を実行。各候補で `researching`→`ready`、結果を `research_*` 列に保存
4. 画面は `ready` 候補のリサーチ結果（profile/stats/achievements/sources）を表示

### commit（昇格）
1. 画面で内容を確認・修正（修正は `draft-watch` が `player_candidates` を直接 UPDATE）
2. 「昇格」 → admin API が `workflow_dispatch`（mode=commit, candidate_ids）を発火
3. Actions が `main_promote.py --mode commit` を実行 → `players`/`stats`/`player_achievements` 作成 → `promote_player_candidate_links` → `committed`

### `.github/workflows/player-promotion.yml`（骨子）
```yaml
on:
  workflow_dispatch:
    inputs:
      mode:          { description: 'research | commit', required: true, default: 'research' }
      candidate_ids: { description: 'comma-separated UUIDs', required: true }
jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: python main_promote.py --mode "${{ inputs.mode }}" --candidate-ids "${{ inputs.candidate_ids }}"
        env:
          GOOGLE_GENAI_API_KEY: ${{ secrets.GOOGLE_GENAI_API_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
```

### `draft-watch` 側トリガ（参考・別リポ実装）
```ts
// app/api/admin/promote-research/route.ts
await fetch(
  'https://api.github.com/repos/toshitaka20/draft-news-crawler/actions/workflows/player-promotion.yml/dispatches',
  { method: 'POST',
    headers: { Authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`, Accept: 'application/vnd.github+json' },
    body: JSON.stringify({ ref: 'main', inputs: { mode: 'research', candidate_ids: ids.join(',') } }) }
)
```

---

## 7. stats 自動投入と出典の両立

- `stats` は自動投入する（人手のレビュー必須にはしない）。
- ただし各 `stats` 行は INSERT 時に出典（`provider`/`source_url`）を `stats.extracted_raw` 相当に保持し、後から検証・差し替え可能にする。
  - 現行 `stats` に出典列が無いため、`research_stats`（jsonb・候補側）を正本として残し、`stats` 本体は表示用とする。
- 数値が複数サイトで食い違う場合はマージ優先度（一球速報優先）で1つを採用しつつ、`research_raw` に全候補値を残す。

---

## 8. 堅牢性・運用

- **403/取得失敗**: 球歴等で失敗したサイトはスキップし、残りで継続。全滅時のみ `failed`。
- **レート制御**: プロバイダごとに `SLEEP_SECONDS`、候補は順次処理。
- **冪等性**: `research` は再実行で上書き（`research_*` を作り直す）。`commit` は既に `status='promoted'`/`research_status='committed'`/`player_id` ありの候補をスキップ。
- **同名対策**: 検索が複数ヒットしたら team/学年/draft_year で絞り込み。確定不能なら候補URLを `research_raw` に残し `ready` にして人が選ぶ。
- **ダミーモード**: 既存の `dummy_mode` を踏襲し、ネットワーク・DBなしでもパイプラインを通す。

---

## 9. モデル割当（Gemini統一・おまかせ）

| 処理 | モデル | 理由 |
|---|---|---|
| 構造化抽出 | `gemini-2.5-flash` | HTMLからの数値抽出の正確性 |
| description/bio 生成 | `gemini-2.5-flash`（必要なら `model_override='gemini-2.5-pro'`） | 材料が揃えば flash で十分。品質を上げたい時だけ pro |

`setup_gemini(model_override)` でモデルを切替可能にする。

---

## 10. 実装順序（フェーズ内ステップ）

1. スキーマ適用（`schema_phase6_player_candidates_promotion.sql`）
2. `research/base.py` ＋ 共通HTTPセッション
3. `research/ikkyu.py`（成績の一次ソース）→ `research/draft_kaigi.py`（評価）
4. `ai/gemini.py`: `structure_player_research_with_gemini`（＋`setup_gemini` 拡張）
5. `research/merge.py`
6. `database/supabase_client.py`: `SupabasePlayerPromotionStore.save_research_result`
7. `main_promote.py --mode research` ＋ `player-promotion.yml`（research経路を先に通す）
8. `ai/gemini.py`: `generate_player_description_with_gemini`（素材＝関連記事＋draft-repo）＋ `fetch_related_articles`
9. `commit_promotion` ＋ `--mode commit`（昇格経路）
10. `research/draft_repo.py` / `research/kyureki.py` を追加（カバレッジ拡充）
11. `draft-watch` 側のトリガAPIとボタン（別リポ）

最初の動作確認ゴールは **7（researchがDBに提案を書く）** まで。そこからcommit経路を足す。

---

## 11. 関連

- 上位ドキュメント: `docs/data_pipeline_strategy.md`「Phase 6」
- 既存スキーマ: `draft_watch_db.md`（players/stats/player_achievements/player_candidates）
- 昇格関数: `database/schema_fix_promote_links_scout_visits.sql`（`promote_player_candidate_links`）
