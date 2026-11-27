"""連盟公式サイトから大学リーグ戦の成績を取り込む。

    PYTHONPATH=. venv/bin/python3 main_stats.py --league big6 --year 2026 --season fall --dry-run
    PYTHONPATH=. venv/bin/python3 main_stats.py --league big6 --year 2026 --season fall

--year/--season を省くと、今の時期のシーズン（4〜7月=春、8月〜翌3月=秋）を対象にする。
--dry-run は DB を変えず、照合結果と変更予定だけ表示する。
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from database.supabase_client import _init_supabase_client
from stats_sync import big6, tohto
from stats_sync.store import StatsStore, apply_changes, is_noop, plan_changes

LEAGUES = {
    'big6': big6,
    'tohto': tohto,
}

JST = timezone(timedelta(hours=9))


def default_season():
    now = datetime.now(JST)
    if 4 <= now.month <= 7:
        return now.year, 'spring'
    return (now.year if now.month >= 8 else now.year - 1), 'fall'


def fmt_row(row):
    if (row.get('innings') or 0) > 0 and not (row.get('at_bats') or 0):
        return (f"{row.get('games')}試合 {row.get('innings')}回 自責{row.get('earned_runs')} "
                f"奪三振{row.get('strikeouts')}")
    return (f"{row.get('games')}試合 {row.get('at_bats')}打数{row.get('hits')}安打 "
            f"{row.get('home_runs')}本 {row.get('rbis')}打点")


def run(league_name: str, year: int, season: str, dry_run: bool) -> int:
    league = LEAGUES[league_name]
    is_dummy, client = _init_supabase_client()
    if is_dummy:
        print('Supabase に接続できません（SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY を確認）')
        return 1
    store = StatsStore(client)
    if not dry_run and not (store.links_available and store.source_column_available):
        print('stats.source 列または player_stat_links がありません。'
              'draft-watch の database_stats_sources.sql を先に実行してください。')
        return 1

    print(f'== {league.TOURNAMENT} {year} {season}（{"試し実行" if dry_run else "書き込み"}）')
    ext_players = league.fetch_season(year, season)
    print(f'連盟サイトの選手: {len(ext_players)}人')

    players = store.load_university_players()
    links = store.load_links(league.SOURCE)
    report = store.match(ext_players, players, links, league.fill_profile)
    print(f'照合できた選手: {len(report.matches)}人'
          f'（対応表から {sum(1 for m in report.matches if m.how == "link")}人）')
    for m in report.matches:
        if m.warnings:
            print(f'  ⚠ {m.player["name"]}（{m.player["team"]}）: {"; ".join(m.warnings)}')
    for ext, cands in report.ambiguous:
        print(f'  ? 決めきれない: {ext.full_name or ext.display_name}（{ext.team}）'
              f' 候補={[c["name"] for c in cands]}')
    for ext, cands in report.unmatched_profiles:
        print(f'  ? 選手ページが読めない: {ext.display_name}（{ext.team}） 候補={[c["name"] for c in cands]}')

    # 同じ大学の登録選手で、連盟の記録に見つからなかった人（出場なし・名前の照合漏れの確認用）
    from stats_sync.store import _teams_match
    ext_teams = {e.team for e in ext_players}
    matched_ids = {m.player['id'] for m in report.matches}
    missing = [p for p in players
               if p['id'] not in matched_ids and any(_teams_match(p.get('team'), t) for t in ext_teams)
               and (p.get('draft_year') or 0) >= (year + 1 if season == 'fall' else year)]
    if missing:
        print(f'  記録に見つからない登録選手（ドラフト{year + 1 if season == "fall" else year}年以降）: '
              + '、'.join(f'{p["name"]}（{p["team"]}）' for p in missing))

    if hasattr(league, 'verify'):
        for line in league.verify(year, season, ext_players):
            print(f'  [答え合わせ] {line}')

    changes = plan_changes(
        store, report.matches, year, season, league.TOURNAMENT,
        source_url_of=lambda ext: league.source_url(ext, year, season),
        is_existing_tournament=league.is_existing_tournament,
    )
    for c in changes:
        mark = '＝' if is_noop(c) else ('🔒' if c.skipped_locked else ('更新' if c.old_rows else '追加'))
        old = ' / '.join(fmt_row(r) for r in c.old_rows) or '-'
        print(f'  {mark} {c.player["name"]}（{c.player["team"]}）{c.kind}: {fmt_row(c.new_row)}  ← 既存 {old}')

    if dry_run:
        print(f'試し実行のため書き込みません（変更予定 {sum(1 for c in changes if not is_noop(c) and not c.skipped_locked)}件）')
        return 0
    saved = store.save_links(report.matches)
    result = apply_changes(store, changes, os.path.join('output', 'stats_backup'),
                           f'{league.SOURCE}_{year}_{season}')
    print(f'対応表に保存: {saved}件 / 成績: 追加{result["inserted"]}行・置き換えで削除{result["deleted"]}行'
          f'・変更なし{result["unchanged"]}行・手直し済みで触らず{result["locked"]}行')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='連盟公式サイトから大学リーグ戦の成績を取り込む')
    parser.add_argument('--league', choices=sorted(LEAGUES), required=True)
    parser.add_argument('--year', type=int)
    parser.add_argument('--season', choices=['spring', 'fall'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    year, season = default_season()
    return run(args.league, args.year or year, args.season or season, args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
