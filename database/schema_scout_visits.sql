-- スカウト視察情報（どの球団が、どの選手を、何人で、いつ視察したか）を
-- 球団 × 選手単位で正規化して保存するテーブル。
--
-- attention_signals は記事・文単位の注目度シグナル（集計値）を扱うのに対し、
-- scout_visits は球団ページ・選手ページの双方から一覧表示できるよう、
-- 1球団 × 1選手 = 1行になるよう正規化して保存する。

create table if not exists public.scout_visits (
  id uuid primary key default gen_random_uuid(),
  crawled_article_id uuid null references public.crawled_articles(id) on delete set null,
  player_id uuid null references public.players(id) on delete set null,
  player_candidate_id uuid null references public.player_candidates(id) on delete set null,
  player_name text null,
  team_key text null,
  person_count integer null,
  event_date date null,
  event_date_text text null,
  event_date_precision text null,
  source_url text,  -- コメント由来の補完視察は出典URLが無い場合があるため nullable（schema_scout_visits_nullable_source_url.sql）
  source_title text null,
  published_at timestamp with time zone null,
  source text null,
  category text null,
  evidence text not null,
  evidence_hash text generated always as (md5(evidence)) stored,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint scout_visits_person_count_check check (person_count is null or person_count >= 0),
  constraint scout_visits_event_date_precision_check check (
    event_date_precision is null or event_date_precision = any (array['exact', 'approximate', 'unknown'])
  )
);

create index if not exists idx_scout_visits_crawled_article_id
  on public.scout_visits using btree (crawled_article_id);

create index if not exists idx_scout_visits_player_id
  on public.scout_visits using btree (player_id);

create index if not exists idx_scout_visits_player_candidate_id
  on public.scout_visits using btree (player_candidate_id);

create index if not exists idx_scout_visits_player_name
  on public.scout_visits using btree (player_name);

create index if not exists idx_scout_visits_team_key
  on public.scout_visits using btree (team_key);

create index if not exists idx_scout_visits_event_date
  on public.scout_visits using btree (event_date desc);

create index if not exists idx_scout_visits_source_url
  on public.scout_visits using btree (source_url);

create unique index if not exists idx_scout_visits_unique_evidence
  on public.scout_visits using btree (
    source_url,
    evidence_hash,
    coalesce(team_key, ''),
    coalesce(player_name, '')
  );

drop trigger if exists update_scout_visits_updated_at on public.scout_visits;
create trigger update_scout_visits_updated_at
before update on public.scout_visits
for each row
execute function public.update_at_column();
