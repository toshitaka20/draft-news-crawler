"""
player_candidates の重複レコードを「氏名 + 学校」キーで名寄せ統合する一回限りの移行スクリプト。

- 同一キーのクラスタごとに代表(survivor)を1件選び、残り(loser)を統合・削除する。
- survivor選定: player_id有 > status(promoted>pending>rejected) > source_count > created_at昇順。
- loser に紐づく scout_comments / attention_signals / scout_visits の player_candidate_id を
  survivor へ付け替え、survivor が player_id を持つ場合は player_id も合わせて補正する。
- survivor に欠けている属性(player_id, name_kana, category, positions 等)は loser から補完する。
- player_id 衝突（loserのpidがsurvivorと異なる）は誤リンクとして破棄し、レポートに明示する。

デフォルトは dry-run（変更なし）。実行は --apply を付ける。
  PYTHONPATH=. venv/bin/python3 scripts/merge_duplicate_candidates.py
  PYTHONPATH=. venv/bin/python3 scripts/merge_duplicate_candidates.py --apply
"""
import argparse
from collections import defaultdict

from database.supabase_client import _init_supabase_client
from utils import normalize_player_key, normalize_school_key

CHILD_TABLES = ['scout_comments', 'attention_signals', 'scout_visits']
STATUS_RANK = {'promoted': 3, 'pending': 2, 'rejected': 1}
# survivor補完で loser から拾う属性（survivorが空のときのみ埋める）。
FILL_FIELDS = [
    'player_id', 'name_kana', 'category', 'positions', 'throws', 'bats',
    'height_cm', 'weight_kg', 'birth_date', 'fastball_max', 'description',
    'team', 'team_name', 'draft_year', 'school_year',
]


def cluster_key(row):
    return (
        normalize_player_key(row.get('name') or '') or '',
        normalize_school_key(row.get('team') or row.get('team_name')) or '',
    )


def pick_survivor(rows):
    # 昇順ソートで先頭を代表に選ぶ:
    #   player_id有(0)を先 → status高を先 → source_count多を先 → created_at古い方を先。
    def key(r):
        return (
            0 if r.get('player_id') else 1,
            -STATUS_RANK.get(r.get('status'), 0),
            -(r.get('source_count') or 0),
            r.get('created_at') or '',
        )
    return sorted(rows, key=key)[0]


def count_children(sb, cand_ids):
    counts = defaultdict(lambda: defaultdict(int))
    for tbl in CHILD_TABLES:
        try:
            res = sb.table(tbl).select('id,player_candidate_id').in_('player_candidate_id', cand_ids).execute()
            for r in res.data or []:
                counts[r['player_candidate_id']][tbl] += 1
        except Exception as e:
            print(f'  [warn] {tbl} 取得失敗: {e}')
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='実際に統合を実行する（既定はdry-run）')
    args = ap.parse_args()

    ok, sb = _init_supabase_client()
    if sb is None:
        print('Supabase未接続'); return

    rows = sb.table('player_candidates').select(
        'id,name,team,team_name,draft_year,status,player_id,source_count,created_at,'
        'name_kana,category,positions,throws,bats,height_cm,weight_kg,birth_date,'
        'fastball_max,description,school_year'
    ).execute().data

    clusters = defaultdict(list)
    for r in rows:
        clusters[cluster_key(r)].append(r)
    dups = {k: v for k, v in clusters.items() if len(v) > 1}

    loser_ids = [r['id'] for v in dups.values() for r in v if r['id'] != pick_survivor(v)['id']]
    child_counts = count_children(sb, loser_ids) if loser_ids else {}

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'=== player_candidates 名寄せ統合 [{mode}] ===')
    print(f'総レコード {len(rows)} 件 / ユニーク {len(clusters)} 人 / 重複クラスタ {len(dups)} 件\n')

    total_deleted = 0
    total_repointed = defaultdict(int)
    for key, members in sorted(dups.items(), key=lambda x: -len(x[1])):
        survivor = pick_survivor(members)
        losers = [r for r in members if r['id'] != survivor['id']]
        print(f'■ {key}  survivor={survivor["id"][:8]} '
              f'({survivor.get("name")!r}/{survivor.get("team")!r}/{survivor.get("status")}/pid={(survivor.get("player_id") or "-")[:8]})')

        # survivor補完値
        fill = {}
        for f in FILL_FIELDS:
            if survivor.get(f) in (None, '', []):
                for l in losers:
                    if l.get(f) not in (None, '', []):
                        fill[f] = l.get(f)
                        break
        # draft_year はクラスタ内の最大（最新年）を採用（player未リンク時のみ）
        if not survivor.get('player_id'):
            years = [m.get('draft_year') for m in members if m.get('draft_year')]
            if years and max(years) != survivor.get('draft_year'):
                fill['draft_year'] = max(years)
        if fill:
            print(f'    補完: {fill}')

        for l in losers:
            cc = dict(child_counts.get(l['id'], {}))
            conflict = ''
            if l.get('player_id') and survivor.get('player_id') and l['player_id'] != survivor['player_id']:
                conflict = f'  ⚠誤リンク破棄 pid={l["player_id"][:8]}→{survivor["player_id"][:8]}'
            print(f'    - loser {l["id"][:8]} ({l.get("team")!r}/{l.get("status")}) '
                  f'children={cc or "なし"}{conflict}')

            if args.apply:
                upd = {'player_candidate_id': survivor['id']}
                if survivor.get('player_id'):
                    upd['player_id'] = survivor['player_id']
                for tbl in CHILD_TABLES:
                    if cc.get(tbl):
                        sb.table(tbl).update(upd).eq('player_candidate_id', l['id']).execute()
                        total_repointed[tbl] += cc[tbl]
                sb.table('player_candidates').delete().eq('id', l['id']).execute()
            total_deleted += 1

        if args.apply and fill:
            sb.table('player_candidates').update(fill).eq('id', survivor['id']).execute()
        print()

    print('=== サマリ ===')
    print(f'統合で削除されるレコード: {total_deleted} 件（{len(rows)} → {len(rows) - total_deleted} 件）')
    if args.apply:
        print(f'子参照の付け替え: {dict(total_repointed)}')
        print('✅ 統合を実行しました。')
    else:
        print('（dry-run。--apply で実行）')


if __name__ == '__main__':
    main()
