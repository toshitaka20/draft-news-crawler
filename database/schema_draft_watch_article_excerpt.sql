-- draft_watch_article_candidates に下書き記事の抜粋カラムを追加する。
--
-- 背景: 記事化候補→記事公開(articles)時、これまで draft-watch 側で本文(markdown)の
-- リード文先頭120字を抜粋に流用していた。そのため「抜粋＝記事冒頭」になり、
-- 選手名のMarkdownリンクもそのまま混入していた。
-- Gemini に専用の抜粋（短く・記事の重要性が伝わる・リンクなしのプレーンテキスト）を
-- 生成させ、この列に保存する。draft-watch の記事作成画面はこの列を優先して使う。
--
-- Supabase SQL エディタで手動適用する。

alter table public.draft_watch_article_candidates
  add column if not exists draft_article_excerpt text;
