# プロ志望届トラッキング（main_pro_aspiring.py）

プロ志望届の公示ページを3時間ごとに巡回し、**Draft-Watchの記事1本を更新し続ける**バッチ。
記事はAI生成せず、名簿をそのまま構造化して出す（数字と氏名が命の記事なので創作の余地を作らない）。

## 対象ソース

| 区分 | URL | 表の列 |
|---|---|---|
| 高校 | `https://www.jhbf.or.jp/pro-aspiring/{year}.html` | 都道府県 / 学校名 / 氏名 / 受付日 |
| 大学 | `https://www.jubf.net/system/prog/procandidate.php?kind=all&year={year}` | 連盟 / 学校名 / 氏名 / ふりがな / 受付日 |

大学側は「NPBドラフト対象者」「NPBドラフト対象外者」の2セクションがあり、後者は
`draft_eligible=False` として記事内でも別の表に分けている。連盟名の「〃」（同上）は直前の行から補完する。

高野連はレスポンスヘッダに charset が無く、requests が ISO-8859-1 と誤判定して文字化けするため、
`scraper/pro_aspiring.py` の `_fetch_html` で meta charset を見て明示的にデコードしている。

## 実行

```bash
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py                 # 通常実行
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --dry-run       # DB・Issueに書かず結果と記事本文を表示
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --no-issues     # Issueだけ触らない
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --no-publish-sync  # 公開記事を更新しない
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --force         # 実行期間（〜10/31）外でも実行
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --bind-article <articles.id>  # 更新対象の公開記事を結び直す
PYTHONPATH=. venv/bin/python3 test/test_pro_aspiring_matching.py   # 名寄せのテスト
PYTHONPATH=. venv/bin/python3 test/test_pro_aspiring_article.py    # 公開記事の部分更新のテスト
```

GitHub Actions: `.github/workflows/pro-aspiring.yml`（`cron: '0 */3 * * *'`）。
10/31（JST）を過ぎた実行はスクリプト側が即終了するので、ワークフローを止め忘れても副作用はない。

## 記事候補（draft_watch_article_candidates）の更新方法

公開記事の元ネタ・履歴として、候補行も毎回更新する（公開記事の本文はこの下書きとは別に、
後述の部分更新で差し替える）。

- `draft_watch_article_candidates` の `topic_key = 'other:pro_aspiring:{year}'` の**1行を毎回上書き**する。
  行が無ければ `status='draft'` で作る。以後 status は触らない（人のレビュー結果を尊重する）。
- 前回の `summary_json.entries` と突き合わせて「前回更新からの新規提出者」を記事の冒頭に出す。
  各エントリの `first_seen_at` も `summary_json` に持つので、状態管理用のテーブルは増やしていない。
- `review_note` は `<!-- pro-aspiring auto -->` マーカーより後ろだけを自動で書き換える。
  マーカーより前に書いた人手のメモは残る。
## 公開記事（articles）の日々更新

公開記事は人が書いたリード・解説・注記を含むので、**本文をまるごと上書きしない**。
見出しを目印に、機械が持っているブロックだけを差し替える（`pro_aspiring_site_article.py`）。

対象記事: `articles.id = aa9dcd7b-de93-435b-bca8-53a73f5d1cd4`
（`draft_watch_article_candidates.published_article_id` に保存。別の記事に付け替えるときは
`--bind-article <articles.id>` を1回付けて実行する）

機械が書き換えるのは以下だけ。それ以外の段落・注記・解説は一切触らない。

| ブロック | 目印 | 中身 |
|---|---|---|
| リードの人数 | `**N月N日時点の提出者は高校生N人・大学生N人の合計N人**` | 日付と人数 |
| 注記の時点 | `（20NN年N月N日…時点）` | 名簿ページを読んだ時刻 |
| 高校生一覧 | `## …高校生…一覧…` | 見出しの `（N人）` と直後の表 |
| 大学生一覧 | `## …大学生…一覧…` | 同上 |
| 未提出の人数 | `N月N日時点で一覧に名前が無い高校生はN人、大学生はN人です` | 人数 |
| 未提出（高校生／大学生） | `## …まだ提出していない…` 配下の `### 高校生` / `### 大学生` | 直後の表 |
| タイトル・抜粋・メタ | `（N月N日時点）` / `高校生N人・大学生N人` / `N月N日時点は…計N人` | 日付と人数のみ |

- **目印の見出しが見つからないブロックは何もせずスキップ**してログに出す。
  記事の構成を変えたときに壊さないための保険。逆に、見出しの文言を大きく変えると
  そのブロックは更新されなくなるので、`## 高校生…一覧` のようなキーワードは残しておく。
- 表の並びは連盟の公表順のまま。ポジションは `players.position`、評価は `players.rank`
  （90=S / 80=A / 70=B / 60=C / 50=D / 40=E / 30=F、それ以外は「—」）を引く。
- 「まだ提出していない主な上位候補」は `players` の評価B以上（rank>=70）かつ名簿に未掲載の選手を
  評価の高い順に並べる（表は各10人まで、人数は全件）。選手が提出すると翌回の実行で自動的に消える。
- 公開記事を触らせたくないときは `--no-publish-sync`。

## 選手の紐付けと declared

- 名簿の氏名を `players` と名寄せし、一致した選手は
  - `declared` が false なら **true に更新**する（志望届提出＝プロ志望表明）
  - 記事本文で選手ページ（`/players/{draft_year}/{id}`）へリンクする
  - `summary_json.linked_player_ids` に記録し、記事が公開されたら `article_players` に紐付ける
    （`article_players` は `articles.id` が必要なので、公開前は紐付けられない）

### 名寄せ（`database/player_matcher.py`）

`players` を全件メモリに載せ、氏名キー → ふりがなキーの順に引く。表記ゆれの吸収:

- 旧字体・異体字: `utils.KYUJITAI_MAP` + `EXTRA_VARIANT_MAP`（岡﨑↔岡崎、髙田↔高田、當山↔当山 など）
- 姓名の区切り: 全角スペース / 半角スペース / 区切りなしを同一視
- ふりがな: カタカナ↔ひらがな、空白除去
- 学校名: `utils.normalize_school_key` + 「附↔付」「ヶ↔ケ」（千葉商科大学↔千葉商科大、金沢学院大附↔金沢学院大付）

複数ヒットしたときは **学校 → カテゴリ → ドラフト年** の順に絞り、それでも一意にならなければ
`ambiguous`（判定保留）として**自動更新も自動リンクもしない**。人が確認するためにIssueを立てる。

未ヒットのときは、同校で名前が似ている登録選手（類似度0.6以上）を「表記ゆれの可能性」として
Issue本文に添える。異体字マップの穴はここから見つけて `EXTRA_VARIANT_MAP` に足していく。

## GitHub トラッカーIssue

未登録（`unmatched`）と判定保留（`ambiguous`）の選手は、**年ごとに1本のトラッカーIssue**で管理する
（志望届は10月末までに200〜300人提出されるので、選手ごとにIssueを立てると埋もれるため）。

- タイトル: `[志望届{year}] 未登録選手トラッカー`（このタイトルでIssueを引く）
- ラベル: `pro-aspiring-{year}`（無ければ自動作成）
- 本文は毎回まるごと書き換える。各行の末尾に `<!--k:...-->` という不可視のキーを埋めてあり、
  **人がチェックした `- [x]` は書き換え後も引き継がれる**
- 増減があった実行だけコメントを足す（新しく未登録になった選手 / 登録されて解消した選手）
- Issue番号は `summary_json.github_issue_number` に持つ。番号が消えてもタイトルで引き直せる
- トークンは `GH_TOKEN` / `GITHUB_TOKEN` / `gh auth token` の順に解決する。無ければIssue操作はスキップされる

選手を登録すると次回の実行でリストから自動的に消えるので、Issueを手で閉じる運用は不要。
