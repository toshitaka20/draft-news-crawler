-- Phase 1: crawler-owned source articles.
-- public.articles remains reserved for Draft-Watch published/draft content.

create table if not exists public.crawled_articles (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  category text null,
  url text not null unique,
  title text not null,
  body text null,
  published_at timestamp with time zone null,
  has_scout_comment_candidate boolean not null default false,
  has_attention_candidate boolean not null default false,
  has_player_candidate boolean not null default false,
  content_hash text null,
  raw jsonb null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create index if not exists idx_crawled_articles_source
  on public.crawled_articles using btree (source);

create index if not exists idx_crawled_articles_published_at
  on public.crawled_articles using btree (published_at);

create index if not exists idx_crawled_articles_candidates
  on public.crawled_articles using btree (
    has_scout_comment_candidate,
    has_attention_candidate,
    has_player_candidate
  );

create index if not exists idx_crawled_articles_content_hash
  on public.crawled_articles using btree (content_hash);

drop trigger if exists update_crawled_articles_updated_at on public.crawled_articles;
create trigger update_crawled_articles_updated_at
before update on public.crawled_articles
for each row
execute function update_at_column();
