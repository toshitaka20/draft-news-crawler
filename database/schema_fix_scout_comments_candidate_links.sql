-- Link scout comments to unapproved player candidates.
--
-- scout_comments previously had only player_id, so scout comments extracted
-- before candidate approval could not be attached to the promoted player later.

alter table public.scout_comments
  add column if not exists player_candidate_id uuid null
    references public.player_candidates(id) on delete set null,
  add column if not exists player_name text null;

create index if not exists idx_scout_comments_player_candidate_id
  on public.scout_comments using btree (player_candidate_id);

create index if not exists idx_scout_comments_player_name
  on public.scout_comments using btree (player_name);

update public.scout_comments sc
set
  player_candidate_id = pcs.player_candidate_id,
  player_name = coalesce(sc.player_name, pc.name)
from public.player_candidate_sources pcs
join public.player_candidates pc on pc.id = pcs.player_candidate_id
where sc.player_id is null
  and sc.player_candidate_id is null
  and sc.source_url = pcs.source_url;

create or replace function public.promote_player_candidate_links(
  p_player_candidate_id uuid,
  p_player_id uuid
)
returns void
language plpgsql
security invoker
as $$
begin
  update public.player_candidates
  set
    player_id = p_player_id,
    status = 'promoted',
    updated_at = now()
  where id = p_player_candidate_id;

  update public.scout_comments
  set player_id = p_player_id
  where player_candidate_id = p_player_candidate_id
    and player_id is null;

  update public.attention_signals
  set player_id = p_player_id
  where player_candidate_id = p_player_candidate_id
    and player_id is null;
end;
$$;

