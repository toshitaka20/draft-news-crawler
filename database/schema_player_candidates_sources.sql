-- Convert player_candidates from per-article rows to aggregated candidate rows.
-- Article-level evidence is stored in player_candidate_sources.

alter table public.player_candidates
  add column if not exists team text null,
  add column if not exists category text null,
  add column if not exists draft_year integer null,
  add column if not exists positions text[] null,
  add column if not exists fastball_max integer null,
  add column if not exists description text null,
  add column if not exists source_count integer not null default 0,
  add column if not exists latest_source_url text null,
  add column if not exists latest_source_title text null,
  add column if not exists latest_evidence text null,
  add column if not exists latest_confidence numeric null;

-- The old design stored one article per player_candidates row, so some
-- production databases still have NOT NULL constraints on article-level
-- columns. The aggregated design keeps article evidence in
-- player_candidate_sources instead.
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


do $$
begin
  if (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'player_candidates'
      and column_name in ('source_url', 'source_title', 'evidence', 'confidence')
  ) = 4 then
    execute $sql$
      update public.player_candidates
      set
        team = coalesce(team, team_name),
        latest_source_url = coalesce(latest_source_url, source_url),
        latest_source_title = coalesce(latest_source_title, source_title),
        latest_evidence = coalesce(latest_evidence, evidence),
        latest_confidence = coalesce(latest_confidence, confidence),
        source_count = greatest(source_count, 1)
      where
        source_url is not null
        or source_title is not null
        or evidence is not null
        or confidence is not null
    $sql$;
  end if;
end;
$$;

create table if not exists public.player_candidate_sources (
  id uuid primary key default gen_random_uuid(),
  player_candidate_id uuid not null references public.player_candidates(id) on delete cascade,
  crawled_article_id uuid null references public.crawled_articles(id) on delete set null,
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

do $$
begin
  if (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'player_candidates'
      and column_name in (
        'crawled_article_id',
        'source_url',
        'source_title',
        'evidence',
        'confidence',
        'extracted_raw',
        'created_at'
      )
  ) = 7 then
    execute $sql$
      insert into public.player_candidate_sources (
        player_candidate_id,
        crawled_article_id,
        source_url,
        source_title,
        evidence,
        confidence,
        extracted_raw,
        created_at
      )
      select
        id,
        crawled_article_id,
        source_url,
        source_title,
        evidence,
        confidence,
        extracted_raw,
        created_at
      from public.player_candidates
      where source_url is not null
        and not exists (
          select 1
          from public.player_candidate_sources existing
          where existing.player_candidate_id = public.player_candidates.id
            and existing.source_url = public.player_candidates.source_url
            and coalesce(existing.evidence, '') = coalesce(public.player_candidates.evidence, '')
        )
    $sql$;
  end if;
end;
$$;

create index if not exists idx_player_candidates_team
  on public.player_candidates using btree (team);

create index if not exists idx_player_candidates_category
  on public.player_candidates using btree (category);

create index if not exists idx_player_candidates_draft_year
  on public.player_candidates using btree (draft_year);

drop index if exists public.idx_player_candidates_unique_source;

create unique index if not exists idx_player_candidates_unique_candidate
  on public.player_candidates using btree (
    name,
    (coalesce(team, team_name, '')),
    (coalesce(draft_year, 0))
  );

create index if not exists idx_player_candidate_sources_candidate_id
  on public.player_candidate_sources using btree (player_candidate_id);

create index if not exists idx_player_candidate_sources_crawled_article_id
  on public.player_candidate_sources using btree (crawled_article_id);

create index if not exists idx_player_candidate_sources_source_url
  on public.player_candidate_sources using btree (source_url);

create index if not exists idx_player_candidate_sources_published_at
  on public.player_candidate_sources using btree (published_at);

create unique index if not exists idx_player_candidate_sources_unique
  on public.player_candidate_sources using btree (
    player_candidate_id,
    source_url,
    (coalesce(md5(evidence), ''))
  );
