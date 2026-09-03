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
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --no-publish-sync  # 公開済み記事の本文は上書きしない
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --force         # 実行期間（〜10/31）外でも実行
PYTHONPATH=. venv/bin/python3 test/test_pro_aspiring_matching.py   # 名寄せのテスト
```

GitHub Actions: `.github/workflows/pro-aspiring.yml`（`cron: '0 */3 * * *'`）。
10/31（JST）を過ぎた実行はスクリプト側が即終了するので、ワークフローを止め忘れても副作用はない。

## 記事の更新方法

- `draft_watch_article_candidates` の `topic_key = 'other:pro_aspiring:{year}'` の**1行を毎回上書き**する。
  行が無ければ `status='draft'` で作る。以後 status は触らない（人のレビュー結果を尊重する）。
- 前回の `summary_json.entries` と突き合わせて「前回更新からの新規提出者」を記事の冒頭に出す。
  各エントリの `first_seen_at` も `summary_json` に持つので、状態管理用のテーブルは増やしていない。
- `review_note` は `<!-- pro-aspiring auto -->` マーカーより後ろだけを自動で書き換える。
  マーカーより前に書いた人手のメモは残る。
- **公開後**（`published_article_id` が入った後）は `articles.title/content/excerpt` も同じ内容へ同期する。
  名簿は10月まで増え続けるので、公開記事を放置すると古い人数のまま残るため。
  公開記事を手で書き換えて運用したくなったら `--no-publish-sync` を付ける。

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
