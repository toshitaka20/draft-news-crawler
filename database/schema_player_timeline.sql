-- Timeline view for player pages.
-- This keeps raw crawled news, scout comments, and attention signals queryable
-- in a single chronological stream.

create or replace view public.player_timeline_items as
select
  pc.player_id,
  pc.id as player_candidate_id,
  pcs.crawled_article_id,
  pcs.source_url,
  coalesce(pcs.source_title, ca.title) as title,
  coalesce(pcs.published_at, ca.published_at) as published_at,
  coalesce(pcs.source, ca.source) as source,
  coalesce(pcs.category, ca.category) as category,
  'candidate'::text as item_type,
  pcs.evidence as body,
  pcs.confidence as confidence,
  null::integer as score,
  pcs.created_at
from public.player_candidate_sources pcs
join public.player_candidates pc on pc.id = pcs.player_candidate_id
left join public.crawled_articles ca on ca.id = pcs.crawled_article_id

union all

select
  sc.player_id,
  null::uuid as player_candidate_id,
  ca.id as crawled_article_id,
  sc.source_url,
  ca.title,
  coalesce(sc.published_at, ca.published_at) as published_at,
  ca.source,
  ca.category,
  'scout_comment'::text as item_type,
  concat_ws(' ', sc.team_name, sc.scout_name, sc.comment) as body,
  null::numeric as confidence,
  null::integer as score,
  sc.created_at
from public.scout_comments sc
left join public.crawled_articles ca on ca.url = sc.source_url
where sc.player_id is not null

union all

select
  ats.player_id,
  ats.player_candidate_id,
  ats.crawled_article_id,
  ats.source_url,
  coalesce(ats.source_title, ca.title) as title,
  coalesce(ats.published_at, ca.published_at) as published_at,
  coalesce(ats.source, ca.source) as source,
  coalesce(ats.category, ca.category) as category,
  'attention'::text as item_type,
  ats.evidence as body,
  null::numeric as confidence,
  ats.score,
  ats.created_at
from public.attention_signals ats
left join public.crawled_articles ca on ca.id = ats.crawled_article_id
where ats.player_id is not null or ats.player_candidate_id is not null;
