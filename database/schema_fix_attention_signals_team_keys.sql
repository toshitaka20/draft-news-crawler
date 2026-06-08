-- attention_signals.teams（日本語球団名の配列）を team_keys（giants/hawksなどのteam_key配列）へ統一する。
-- Draft-Watchサイト側の team_key 表記（draft_predictions / drafted_players などと同じ）に揃えるための変更。

alter table public.attention_signals
  rename column teams to team_keys;

alter index if exists idx_attention_signals_teams
  rename to idx_attention_signals_team_keys;
