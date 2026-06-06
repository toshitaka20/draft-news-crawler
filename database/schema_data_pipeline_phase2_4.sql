-- Phase 2-4: crawler-derived review and Draft-Watch candidate tables.
-- public.articles remains reserved for Draft-Watch published/draft content.

create extension if not exists pgcrypto;

create or replace function public.update_at_column()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.player_candidates (
  id uuid primary key default gen_random_uuid(),
  crawled_article_id uuid null references public.crawled_articles(id) on delete set null,
  player_id uuid null references public.players(id) on delete set null,
  name text not null,
  name_kana text null,
  team text null,
  team_name text null,
  category text null,
  draft_year integer null,
  school_year text null,
  position text null,
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

create index if not exists idx_player_candidates_crawled_article_id
  on public.player_candidates using btree (crawled_article_id);

create index if not exists idx_player_candidates_player_id
  on public.player_candidates using btree (player_id);

create index if not exists idx_player_candidates_name
  on public.player_candidates using btree (name);

create index if not exists idx_player_candidates_team
  on public.player_candidates using btree (team);

create index if not exists idx_player_candidates_category
  on public.player_candidates using btree (category);

create index if not exists idx_player_candidates_draft_year
  on public.player_candidates using btree (draft_year);

create index if not exists idx_player_candidates_status
  on public.player_candidates using btree (status);

create index if not exists idx_player_candidates_created_at
  on public.player_candidates using btree (created_at);

create unique index if not exists idx_player_candidates_unique_source
  on public.player_candidates using btree (
    name,
    (coalesce(team, team_name, '')),
    (coalesce(draft_year, 0))
  );

drop trigger if exists update_player_candidates_updated_at on public.player_candidates;
create trigger update_player_candidates_updated_at
before update on public.player_candidates
for each row
execute function public.update_at_column();

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

create table if not exists public.player_article_sources (
  id uuid primary key default gen_random_uuid(),
  player_id uuid not null references public.players(id) on delete cascade,
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
  constraint player_article_sources_confidence_check check (
    confidence is null or (confidence >= 0 and confidence <= 1)
  )
);

create index if not exists idx_player_article_sources_player_id
  on public.player_article_sources using btree (player_id);

create index if not exists idx_player_article_sources_crawled_article_id
  on public.player_article_sources using btree (crawled_article_id);

create index if not exists idx_player_article_sources_source_url
  on public.player_article_sources using btree (source_url);

create index if not exists idx_player_article_sources_published_at
  on public.player_article_sources using btree (published_at);

create unique index if not exists idx_player_article_sources_unique
  on public.player_article_sources using btree (
    player_id,
    source_url,
    (coalesce(md5(evidence), ''))
  );

create table if not exists public.attention_signals (
  id uuid primary key default gen_random_uuid(),
  crawled_article_id uuid null references public.crawled_articles(id) on delete set null,
  player_id uuid null references public.players(id) on delete set null,
  player_candidate_id uuid null references public.player_candidates(id) on delete set null,
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
  evidence_hash text generated always as (md5(evidence)) stored,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint attention_signals_team_count_check check (team_count >= 0),
  constraint attention_signals_person_count_check check (person_count >= 0),
  constraint attention_signals_score_check check (score >= 0)
);

create index if not exists idx_attention_signals_crawled_article_id
  on public.attention_signals using btree (crawled_article_id);

create index if not exists idx_attention_signals_player_id
  on public.attention_signals using btree (player_id);

create index if not exists idx_attention_signals_player_candidate_id
  on public.attention_signals using btree (player_candidate_id);

create index if not exists idx_attention_signals_player_name
  on public.attention_signals using btree (player_name);

create index if not exists idx_attention_signals_source_url
  on public.attention_signals using btree (source_url);

create index if not exists idx_attention_signals_published_at
  on public.attention_signals using btree (published_at);

create index if not exists idx_attention_signals_score
  on public.attention_signals using btree (score desc);

create index if not exists idx_attention_signals_has_mlb
  on public.attention_signals using btree (has_mlb);

create index if not exists idx_attention_signals_teams
  on public.attention_signals using gin (teams);

create unique index if not exists idx_attention_signals_unique_evidence
  on public.attention_signals using btree (
    source_url,
    evidence_hash
  );

drop trigger if exists update_attention_signals_updated_at on public.attention_signals;
create trigger update_attention_signals_updated_at
before update on public.attention_signals
for each row
execute function public.update_at_column();

create table if not exists public.draft_watch_article_candidates (
  id uuid primary key default gen_random_uuid(),
  topic_key text null,
  topic_type text not null,
  main_player_id uuid null references public.players(id) on delete set null,
  main_player_name text null,
  title text not null,
  importance_score integer not null default 0,
  source_urls text[] not null default array[]::text[],
  summary_json jsonb null,
  draft_article_markdown text null,
  published_article_id uuid null references public.articles(id) on delete set null,
  review_note text null,
  status text not null default 'draft',
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint draft_watch_article_candidates_status_check check (
    status = any (array['draft', 'reviewed', 'published', 'rejected'])
  ),
  constraint draft_watch_article_candidates_topic_type_check check (
    topic_type = any (array['player_watch', 'scout_meeting', 'game_report', 'ranking', 'other'])
  ),
  constraint draft_watch_article_candidates_importance_score_check check (
    importance_score >= 0
  )
);

create unique index if not exists idx_draft_watch_article_candidates_topic_key
  on public.draft_watch_article_candidates using btree (topic_key)
  where topic_key is not null;

create index if not exists idx_draft_watch_article_candidates_status
  on public.draft_watch_article_candidates using btree (status);

create index if not exists idx_draft_watch_article_candidates_topic_type
  on public.draft_watch_article_candidates using btree (topic_type);

create index if not exists idx_draft_watch_article_candidates_importance_score
  on public.draft_watch_article_candidates using btree (importance_score desc);

create index if not exists idx_draft_watch_article_candidates_main_player_id
  on public.draft_watch_article_candidates using btree (main_player_id);

create index if not exists idx_draft_watch_article_candidates_published_article_id
  on public.draft_watch_article_candidates using btree (published_article_id);

create index if not exists idx_draft_watch_article_candidates_created_at
  on public.draft_watch_article_candidates using btree (created_at);

create index if not exists idx_draft_watch_article_candidates_source_urls
  on public.draft_watch_article_candidates using gin (source_urls);

drop trigger if exists update_draft_watch_article_candidates_updated_at
  on public.draft_watch_article_candidates;
create trigger update_draft_watch_article_candidates_updated_at
before update on public.draft_watch_article_candidates
for each row
execute function public.update_at_column();

create table if not exists public.draft_watch_article_candidate_sources (
  id uuid primary key default gen_random_uuid(),
  draft_watch_article_candidate_id uuid not null
    references public.draft_watch_article_candidates(id) on delete cascade,
  crawled_article_id uuid null references public.crawled_articles(id) on delete set null,
  source_url text not null,
  role text not null default 'source',
  created_at timestamp with time zone not null default now(),
  constraint draft_watch_article_candidate_sources_role_check check (
    role = any (array['primary', 'source', 'supporting'])
  )
);

create index if not exists idx_draft_watch_article_candidate_sources_candidate_id
  on public.draft_watch_article_candidate_sources using btree (draft_watch_article_candidate_id);

create index if not exists idx_draft_watch_article_candidate_sources_crawled_article_id
  on public.draft_watch_article_candidate_sources using btree (crawled_article_id);

create index if not exists idx_draft_watch_article_candidate_sources_source_url
  on public.draft_watch_article_candidate_sources using btree (source_url);

create unique index if not exists idx_draft_watch_article_candidate_sources_unique
  on public.draft_watch_article_candidate_sources using btree (
    draft_watch_article_candidate_id,
    source_url
  );
