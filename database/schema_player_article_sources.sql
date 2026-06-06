-- Article-level evidence for players that already exist in public.players.
-- This complements player_candidate_sources, which is for unapproved candidates.

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
