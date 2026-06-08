-- promote_player_candidate_links() が選手候補の昇格時に player_id を伝播する対象に
-- scout_visits（視察情報）を追加する。
--
-- scout_comments / attention_signals は既存実装で対応済みだが、
-- scout_visits は後から追加されたテーブルのため伝播対象に含まれていなかった。

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

  update public.scout_visits
  set player_id = p_player_id
  where player_candidate_id = p_player_candidate_id
    and player_id is null;
end;
$$;
