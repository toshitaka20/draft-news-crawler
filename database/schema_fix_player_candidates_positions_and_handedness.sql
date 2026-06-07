-- Add normalized player candidate positions and handedness fields.
--
-- positions is the canonical multi-position field. The legacy position text
-- column is migrated into positions and then removed.

alter table public.player_candidates
  add column if not exists positions text[] null;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'player_candidates'
      and column_name = 'position'
  ) then
    update public.player_candidates
    set positions = case
      when position is null or btrim(position) = '' then positions
      when position like '%投手%' and position like '%外野手%' then array['投手', '外野手']::text[]
      when position like '%投手%' and position like '%内野手%' then array['投手', '内野手']::text[]
      when position like '%投手%' and position like '%捕手%' then array['投手', '捕手']::text[]
      when position like '%捕手%' then array['捕手']::text[]
      when position like '%内野手%' then array['内野手']::text[]
      when position like '%外野手%' then array['外野手']::text[]
      when position like '%投手%' then array['投手']::text[]
      else array[position]::text[]
    end
    where positions is null
      and position is not null
      and btrim(position) <> '';
  end if;
end;
$$;

alter table public.player_candidates
  drop column if exists position;

update public.player_candidates
set throws = case
  when throws = 'R' or throws like '%右%' then 'R'
  when throws = 'L' or throws like '%左%' then 'L'
  else throws
end
where throws is not null;

update public.player_candidates
set bats = case
  when bats = 'S' or bats like '%両%' or bats like '%スイッチ%' then 'S'
  when bats = 'R' or bats like '%右%' then 'R'
  when bats = 'L' or bats like '%左%' then 'L'
  else bats
end
where bats is not null;
