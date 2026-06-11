"""
scout_visits の既存重複（同一選手×同一球団×同一日の視察が、Yahoo転載と元記事で別レコード）を
1件へ統合する一回限りの移行。デフォルト dry-run、--apply で実行。

- 重複判定キー: (選手参照, team_key, event_date)。選手参照 = player_id > player_candidate_id > 正規化氏名。
  ※ event_date が不明(null)同士は同一視（同じ視察を複数媒体が報じたケース）。日付が判明していれば別日は別視察として残す。
- survivor選定: event_date有を優先 → 元記事(news.yahoo.co.jp以外)を優先 → created_at古い順。
- scout_visits は葉テーブルなので loser は単純削除。

  PYTHONPATH=. venv/bin/python3 scripts/dedup_scout_visits.py
  PYTHONPATH=. venv/bin/python3 scripts/dedup_scout_visits.py --apply
"""
import argparse
from collections import defaultdict

from database.supabase_client import _init_supabase_client, SupabaseScoutVisitStore
from utils import normalize_player_key


def fetch_all(sb, cols):
    rows, start = [], 0
    while True:
        chunk = sb.table('scout_visits').select(cols).order('id').range(start, start + 999).execute().data or []
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        start += 1000
    return rows


def survivor_order(r):
    src = r.get('source_url') or ''
    return (
        0 if (r.get('event_date') or '').strip() else 1,
        1 if 'news.yahoo.co.jp' in src else 0,
        r.get('created_at') or '',
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    ok, sb = _init_supabase_client()
    if sb is None:
        print('Supabase未接続'); return

    rows = fetch_all(sb, 'id,player_id,player_candidate_id,player_name,team_key,event_date,source_url,created_at,evidence')
    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'=== scout_visits 重複統合 [{mode}] === 総 {len(rows)} 件\n')

    # (1) 同一キー(選手×球団×日)の重複を1件へ。
    groups = defaultdict(list)
    for r in rows:
        key = SupabaseScoutVisitStore.visit_dedup_key(
            r.get('player_id'), r.get('player_candidate_id'),
            r.get('player_name'), r.get('team_key'), r.get('event_date'))
        groups[key].append(r)

    del_ids = set()
    survivors = []  # (ref, team) 単位の後処理用に代表を集める
    dup_clusters = [(k, sorted(v, key=survivor_order)) for k, v in groups.items() if len(v) > 1]
    for key, members in dup_clusters:
        survivor = members[0]
        print(f'■ {key}  ({members[0].get("player_name")})')
        print(f'    keep {survivor["id"][:8]} ({(survivor.get("source_url") or "")[:34]}, date={survivor.get("event_date") or "-"})')
        for l in members[1:]:
            print(f'    - del {l["id"][:8]} ({(l.get("source_url") or "")[:34]}, date={l.get("event_date") or "-"})')
            del_ids.add(l['id'])
    for key, members in groups.items():
        survivors.append((key, members[0]))

    # (2) 日付なしの視察は、同一(選手×球団)に日付ありの視察があれば吸収して削除する。
    by_player_team = defaultdict(list)
    for (ref, team, date), surv in survivors:
        by_player_team[(ref, team)].append((date, surv))
    absorbed = 0
    for (ref, team), items in by_player_team.items():
        # 球団が空(不明/全球団)のときは別球団を誤統合しうるため吸収しない。
        if not team:
            continue
        has_dated = any(d for d, _ in items)
        if not has_dated:
            continue
        for d, surv in items:
            if not d and surv['id'] not in del_ids:
                print(f'■ 日付なし吸収 ({ref[:8]},{team}) → 日付あり視察へ統合: del {surv["id"][:8]} ({(surv.get("source_url") or "")[:30]})')
                del_ids.add(surv['id'])
                absorbed += 1

    print(f'\n削除対象: {len(del_ids)} 件（同キー重複 {len(del_ids) - absorbed} + 日付なし吸収 {absorbed}）')

    if args.apply and del_ids:
        for cid in del_ids:
            sb.table('scout_visits').delete().eq('id', cid).execute()
        print(f'\n✅ 削除 {len(del_ids)} 件（{len(rows)} → {len(rows) - len(del_ids)} 件）')
    elif not args.apply:
        print('\n（dry-run。--apply で実行）')


if __name__ == '__main__':
    main()
