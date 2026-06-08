-- Phase 6: 選択候補のリサーチ付き昇格（C案）
-- player_candidates を「リサーチ結果の受け皿」にする最小スキーマ。
-- players のミラー列は追加せず、昇格案を research_payload(jsonb) に丸ごと保存する。
-- 詳細設計: docs/phase6_player_promotion_design.md

alter table public.player_candidates
  add column if not exists research_payload jsonb,                       -- 昇格案JSON（player/stats/achievements/sources/notes）
  add column if not exists research_status  text not null default 'none', -- none/queued/researching/ready/committed/failed
  add column if not exists researched_at    timestamptz;                  -- 最終リサーチ時刻

do $$
begin
  alter table public.player_candidates
    add constraint player_candidates_research_status_check
    check (research_status in ('none','queued','researching','ready','committed','failed'));
exception
  when duplicate_object then null;
end $$;

create index if not exists idx_player_candidates_research_status
  on public.player_candidates (research_status);
