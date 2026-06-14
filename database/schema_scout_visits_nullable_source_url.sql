-- scout_visits.source_url の NOT NULL を解除する。
--
-- 背景: 「スカウトコメントが付く＝その球団は視察している」前提で、既存 scout_comments から
-- 視察(scout_visits)を補完する（scripts/backfill_visits_from_comments.py）。
-- 古いコメントには出典記事URL(source_url)が記録されていないものが多数あり、source_url が
-- NOT NULL だと視察化できずコメントが付いているのに視察が出ない不整合が生じていた。
-- 出典URLが無いコメント由来の視察も登録できるよう NULL 許可にする。
--
-- 表示側(draft-watch)は source_url が空ならリンクを出さない作りのため、NULL でも壊れない。
-- ユニークインデックス idx_scout_visits_unique_evidence は source_url を素のカラムで含むため、
-- NULL 同士は Postgres 上で別行扱い（NULL != NULL）となり衝突しない。視察の重複は
-- backfill 側の (選手参照 × team_key) 名寄せで抑止する。
--
-- Supabase SQL エディタで手動適用する。

alter table public.scout_visits
  alter column source_url drop not null;
