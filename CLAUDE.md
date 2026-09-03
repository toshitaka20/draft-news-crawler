# CLAUDE.md

プロ野球ドラフト情報のクローラ＆データパイプライン。記事をクロール→選手候補/スカウトコメント/注目シグナルを抽出→Supabaseに蓄積し、Draft-Watch記事候補や選手データを生成する。

公開サイト・管理画面は**別リポ `draft-watch`**（`/Users/hirabayashitoshitaka/draft-watch`、Next.js+OpenNext+Cloudflare Workers）。両リポは**Supabaseを結合点に疎結合**。重い処理（スクレイピング＋LLM）はこのリポ、画面とトリガは draft-watch が担う。

## 主要コマンド

```bash
# クロール（記事収集→抽出→DB保存）
PYTHONPATH=. venv/bin/python3 main_regular.py
PYTHONPATH=. venv/bin/python3 main_yahoo_sponavi.py

# Draft-Watch記事候補バッチ（毎朝cron）
PYTHONPATH=. venv/bin/python3 main_draft_watch.py
PYTHONPATH=. venv/bin/python3 main_draft_watch.py --regenerate          # 既存draft候補を再生成
PYTHONPATH=. venv/bin/python3 main_draft_watch.py --regenerate-missing  # 本文未生成のみ

# プロ志望届トラッキング（3時間ごとcron・10月末まで）。名簿記事1本を更新し続ける
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py
PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --dry-run    # DB・Issueに書かず結果だけ表示

# 選手候補の昇格（Phase 6）。リサーチ・JSON作成は Claude Code が担当
PYTHONPATH=. venv/bin/python3 main_promote.py --mode list                                       # 候補一覧（pending）
PYTHONPATH=. venv/bin/python3 main_promote.py --mode promote --file output/promote_drafts/xxx.json  # import+commit一発
```

## 実行時の注意

- Pythonは必ず `PYTHONPATH=. venv/bin/python3` で実行する。
- **システムの `python3`/pyenv shim は使わない**（このサンドボックスでOOM kill されることがある）。
- バルク編集を heredoc + python で回さない（同上）。ファイル編集は Edit/Write ツールで行う。

## Phase 6: 選手候補の昇格案JSON作成ルール

選手データ（成績・実績・description）を作るときは、**DBへ直接 INSERT/UPDATE しない**。必ず昇格案JSONを
`output/promote_drafts/{candidate_id}.json` に出力する（取り込み・昇格は import-draft / commit に任せる）。
詳細設計: `docs/phase6_player_promotion_design.md`。

JSONルール:
- **不明な値は推測せず `null`**。各 stats/achievement に `source_url` を必ず付ける。
- 4サイト（一球速報 `baseball.omyutech.com` / `player.draft-kaigi.jp` / `draft-repo.com` / 球歴 `kyureki.com`）を優先しつつ、**広くリサーチして複数ソースでクロスチェック**。成績がソース間で食い違う場合は `notes` に差異と要確認点を記録する。
- `description` は **DB内の関連記事（crawled_articles / scout_comments / attention_signals）を主役に、Webの記事・プロフィールも使って充実させる**（素材サイトは限定しない）。ただし外部記事をそのまま転載・言い換えせず独自に整理する。数値・評価の羅列にしない。出典は `sources` に残す。
- `stats.season`: `spring` / `summer` / `fall`（英語・DB側 NOT NULL）。**年度集計しか取れずseason別に分けられない成績は stats に入れない**（descriptionで触れる）。`stats.tournament`: **必須**（リーグ名など。`null` にしない）。
- **投手成績と打撃成績は別レコード**にする（1行に混在させない）。投手行は `innings`/`era`/`strikeouts` 等、打撃行は `at_bats`/`hits`/`avg` 等の列で区別される。二刀流は投手行と打撃行を両方並べる。`stats.period`（段階 high_school/university/company）は commit 時に選手 category から自動付与されるので JSON に書かない。
- 指標（防御率・WHIP・出塁率・長打率・OPS）は**アプリが内訳から再計算して表示する**ため、計算済み値だけでなく**内訳を必ず入れる**。投手: `earned_runs`(自責点)/`hits_allowed`(被安打)/`walks`(与四球)/`hit_by_pitch`(与死球)/`walks_plus_hit_by_pitch`(与四死球)。打撃: `walks`/`hit_by_pitch`/`sacrifice_flies`/`doubles`/`triples`/`batter_strikeouts`(打者三振)。内訳が無いと画面で防御率0などになる。
- `achievements.type`: `title` / `national_tournament` / `samurai_japan` のいずれか。
- `rank`: 運営が手動設定するため **0 固定**（リサーチで埋めない）。
- `declared`: プロ志望表明または**進路の記載がなければ `true`**、進学・社会人入りなど**プロ以外の進路が判明していれば `false`**。
- player フィールドは players テーブルに対応（`positions`→`position` / `throws`→`throw` / `bats`→`bat`）。値は**日本語で書いてOK**（commit時にコード変換する: category `大学`→`university` 等、throw/bat `右`→`R`/`左`→`L`/`両`→`S`、position は日本語のまま）。`career`（所属校歴 `["高校名","大学名"]`）や `bio`・`breaking_balls` など players の項目も忘れず埋める。`name_kana`（ふりがな）は DB側 **NOT NULL** なので必ず取得して入れる。
- commit時、同名（スペース除去で正規化）＋draft_yearで既存playerを照合し、存在すれば**新規作成せず既存playerにリンク**する（手作業INSERT等との重複登録防止・氏名表記ゆれの名寄せ）。

## ドキュメント

- データパイプライン全体: `docs/data_pipeline_strategy.md`
- プロ志望届トラッキング: `docs/pro_aspiring_tracking.md`
- DBスキーマ: `draft_watch_db.md`
- Phase 6 詳細設計: `docs/phase6_player_promotion_design.md`
