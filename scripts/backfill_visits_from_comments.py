"""
既存スカウトコメント(scout_comments)から視察(scout_visits)を補完する一回限りの移行。
「スカウトコメントが付く＝その球団は必ずその選手を視察している」という前提で、
球団が特定できるコメントについて、対応する視察レコードが無ければ日付なし視察として追加する。
デフォルト dry-run、--apply で実行。

- 視察化対象: team_name が team_key に正規化できるコメントのみ（other/不明は対象外）。
- 同一性キー: SupabaseScoutVisitStore.visit_dedup_key（選手参照×team_key×日付）。日付は不明(None)。
- 既存 scout_visits に同一(選手×球団)の視察があれば（日付の有無を問わず）追加しない。
- 同一(選手×球団)のコメントが複数あっても視察は1件にまとめる。

  PYTHONPATH=. venv/bin/python3 scripts/backfill_visits_from_comments.py
  PYTHONPATH=. venv/bin/python3 scripts/backfill_visits_from_comments.py --apply
"""
import argparse
from collections import defaultdict

from database.supabase_client import (
    _init_supabase_client, SupabaseScoutVisitStore, SupabaseCrawledArticleStore,
)
from ai.gemini import _scout_team_to_npb_key


def fetch_all(sb, table, cols):
    rows, start = [], 0
    while True:
        chunk = sb.table(table).select(cols).order('id').range(start, start + 999).execute().data or []
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        start += 1000
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--allow-null-url', action='store_true',
                    help='source_url が無いコメントも視察化する（scout_visits.source_url の NOT NULL 解除が前提）')
    args = ap.parse_args()
    ok, sb = _init_supabase_client()
    if sb is None:
        print('Supabase未接続'); return

    mode = 'APPLY' if args.apply else 'DRY-RUN'

    # 既存視察の同一性キー（選手×球団×日付）と、(選手×球団) ペアを取得する。
    visits = fetch_all(sb, 'scout_visits',
                       'player_id,player_candidate_id,player_name,team_key,event_date')
    existing_keys = set()
    existing_pairs = set()  # (ref, team_key) … 日付有無を問わず既に視察があるペア
    for v in visits:
        ref, team, date = SupabaseScoutVisitStore.visit_dedup_key(
            v.get('player_id'), v.get('player_candidate_id'),
            v.get('player_name'), v.get('team_key'), v.get('event_date'))
        existing_keys.add((ref, team, date))
        if team:
            existing_pairs.add((ref, team))

    comments = fetch_all(sb, 'scout_comments',
                         'id,player_id,player_candidate_id,player_name,team_name,comment,published_at,source_url')
    print(f'=== コメント→視察 補完 [{mode}] === scout_comments {len(comments)} 件 / 既存視察 {len(visits)} 件\n')

    # 球団が特定できるコメントだけを (選手×球団) で束ね、代表コメントを1件選ぶ。
    by_pair = {}
    skipped_no_team = 0
    skipped_orphan = 0
    skipped_no_url = 0
    for c in comments:
        team_key = _scout_team_to_npb_key(c.get('team_name'))
        if not team_key:
            skipped_no_team += 1
            continue
        # 選手参照が一切ないコメントは視察化しても紐づかないため除外。
        if not (c.get('player_id') or c.get('player_candidate_id') or c.get('player_name')):
            skipped_orphan += 1
            continue
        # source_url は scout_visits で NOT NULL のため、既定では出典なしコメントを除外。
        # --allow-null-url 指定時（NOT NULL 解除後）は source_url=null で視察化する。
        if not (c.get('source_url') or '').strip() and not args.allow_null_url:
            skipped_no_url += 1
            continue
        ref, team, _ = SupabaseScoutVisitStore.visit_dedup_key(
            c.get('player_id'), c.get('player_candidate_id'),
            c.get('player_name'), team_key, None)
        pair = (ref, team)
        # 同一ペアは1件に。出典付きを優先（source_url有 → published_at新しい順）。
        cur = by_pair.get(pair)
        if cur is None or (
            (bool(c.get('source_url')), c.get('published_at') or '') >
            (bool(cur.get('source_url')), cur.get('published_at') or '')
        ):
            by_pair[pair] = c

    # 既存視察に無いペアだけを新規視察にする。
    to_insert = []
    for (ref, team), c in by_pair.items():
        if (ref, team) in existing_pairs:
            continue
        if (ref, team, '') in existing_keys:
            continue
        to_insert.append((ref, team, c))

    print(f'球団特定不可でスキップ: {skipped_no_team} 件')
    print(f'選手参照なしでスキップ: {skipped_orphan} 件')
    print(f'出典URLなしでスキップ: {skipped_no_url} 件')
    print(f'視察化対象ペア(選手×球団): {len(by_pair)} 件')
    print(f'既存視察と重複せず新規追加するペア: {len(to_insert)} 件\n')

    source_urls = sorted({c.get('source_url') for _, _, c in to_insert if c.get('source_url')})
    # URLが多いと .in_() のクエリ長で400になるためチャンク分割で取得する。
    store = SupabaseCrawledArticleStore(dummy_mode=False)
    crawled_id_map = {}
    for i in range(0, len(source_urls), 100):
        crawled_id_map.update(store.get_article_id_map_by_urls(source_urls[i:i + 100]))

    records = []
    for ref, team, c in to_insert:
        src = c.get('source_url') or ''
        records.append({
            'crawled_article_id': crawled_id_map.get(src),
            'player_id': c.get('player_id'),
            'player_candidate_id': c.get('player_candidate_id'),
            'player_name': c.get('player_name'),
            'team_key': team,
            'person_count': None,
            'event_date': None,
            'event_date_text': None,
            'event_date_precision': None,
            'source_url': c.get('source_url'),
            'source_title': None,
            'published_at': c.get('published_at'),
            'source': 'Yahoo!スポーツナビ' if 'news.yahoo.co.jp' in src else None,
            'category': None,
            'evidence': (c.get('comment') or '').strip()
                        or f"{c.get('team_name')}のスカウトコメントあり（視察と判断）",
        })

    for r in records[:30]:
        print(f'  + {r.get("player_name")}  {r.get("team_key")}  ({(r.get("source_url") or "-")[:40]})')
    if len(records) > 30:
        print(f'  … 他 {len(records) - 30} 件')

    if args.apply and records:
        # DB側のユニーク制約(idx_scout_visits_unique_evidence: source_url×evidence_hash×team_key×player_name)
        # と当方のdedup(選手参照×球団)は別軸のため、衝突は1件ずつ握りつぶす。バッチINSERTは原子的で全滅する。
        inserted = 0
        dup = 0
        err = 0
        for r in records:
            try:
                sb.table('scout_visits').insert(r).execute()
                inserted += 1
            except Exception as e:
                msg = str(e)
                if '23505' in msg or 'duplicate key' in msg:
                    dup += 1
                else:
                    err += 1
                    if err <= 5:
                        print(f'  [ERR] {r.get("player_name") or r.get("player_id")}/{r.get("team_key")}: {msg[:120]}')
        print(f'\n✅ scout_visits へ {inserted} 件追加 / 既存重複スキップ {dup} 件 / エラー {err} 件'
              f'（{len(visits)} → {len(visits) + inserted} 件）')
    elif not args.apply:
        print('\n（dry-run。--apply で実行）')


if __name__ == '__main__':
    main()
