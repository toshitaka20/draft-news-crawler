-- Hotfix for existing production databases that were created with the old
-- per-article player_candidates design.
--
-- Run this before executing the crawler with the aggregated candidate flow.
-- New article-level evidence is stored in player_candidate_sources, so these
-- legacy player_candidates columns must be nullable.

do $$
declare
  legacy_column text;
begin
  foreach legacy_column in array array[
    'crawled_article_id',
    'source_url',
    'source_title',
    'evidence',
    'confidence'
  ]
  loop
    if exists (
      select 1
      from information_schema.columns
      where table_schema = 'public'
        and table_name = 'player_candidates'
        and column_name = legacy_column
    ) then
      execute format(
        'alter table public.player_candidates alter column %I drop not null',
        legacy_column
      );
    end if;
  end loop;
end;
$$;
