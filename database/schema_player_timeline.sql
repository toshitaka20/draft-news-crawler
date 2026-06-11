-- Timeline view for player pages.
-- This keeps raw crawled news, scout comments, and attention signals queryable
-- in a single chronological stream.

create or replace view public.player_timeline_items
with (security_invoker = true)
as
-- ニュース記事項目（候補根拠 + 登録選手根拠）は、同一ニュースをYahooと元媒体が報じて重複する。
-- 同一選手×正規化タイトル単位で1件に絞り、元媒体（非Yahoo）を優先して残す。
with news_items as (
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
    pas.player_id,
    null::uuid as player_candidate_id,
    pas.crawled_article_id,
    pas.source_url,
    coalesce(pas.source_title, ca.title) as title,
    coalesce(pas.published_at, ca.published_at) as published_at,
    coalesce(pas.source, ca.source) as source,
    coalesce(pas.category, ca.category) as category,
    'player_article'::text as item_type,
    pas.evidence as body,
    pas.confidence as confidence,
    null::integer as score,
    pas.created_at
  from public.player_article_sources pas
  left join public.crawled_articles ca on ca.id = pas.crawled_article_id
),
news_deduped as (
  select *,
    row_number() over (
      partition by
        player_id,
        coalesce(nullif(lower(regexp_replace(coalesce(title, ''), '\s', '', 'g')), ''), source_url, crawled_article_id::text)
      order by
        case when source ilike 'Yahoo%' then 1 else 0 end,  -- 元媒体を優先しYahoo転載を後回し
        published_at desc nulls last,
        created_at
    ) as rn
  from news_items
)
select
  player_id, player_candidate_id, crawled_article_id, source_url, title, published_at,
  source, category, item_type, body, confidence, score, created_at
from news_deduped
where rn = 1

union all

select
  sc.player_id,
  sc.player_candidate_id,
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
where sc.player_id is not null or sc.player_candidate_id is not null

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
where ats.player_id is not null or ats.player_candidate_id is not null

union all

select
  ap.player_id,
  null::uuid as player_candidate_id,
  null::uuid as crawled_article_id,
  null::text as source_url,
  a.title,
  a.published_at,
  'Draft-Watch'::text as source,
  a.category,
  'draft_watch_article'::text as item_type,
  coalesce(a.excerpt, a.meta_description) as body,
  null::numeric as confidence,
  null::integer as score,
  ap.created_at
from public.article_players ap
join public.articles a on a.id = ap.article_id
where ap.player_id is not null;
