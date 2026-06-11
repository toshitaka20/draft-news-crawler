"""
scout_comments の既存データを (1) 鉤括弧「」の除去で表記統一し、(2) 同一選手×同内容の
重複（Yahoo転載と元記事、「」有無・スカウト名表記ゆれ等）を1件へ統合する一回限りの移行。

- コメントは normalize_comment_text で前後の鉤括弧・引用符・空白を除去して更新する。
- 重複判定キー: (選手参照, 正規化コメントキー)。選手参照 = player_id > player_candidate_id > player_name。
  ※1つのコメントが複数選手に言及して選手ごとに登録されたものは別選手＝別レコードとして残す。
- survivor選定: scout_name有を優先 → 元記事(news.yahoo.co.jp以外)を優先 → created_at古い順。
- scout_comments は他テーブルから参照されない葉なので、loserは単純削除。

デフォルト dry-run。実行は --apply。
  PYTHONPATH=. venv/bin/python3 scripts/normalize_dedup_scout_comments.py
  PYTHONPATH=. venv/bin/python3 scripts/normalize_dedup_scout_comments.py --apply
"""
import argparse
from collections import defaultdict

from database.supabase_client import _init_supabase_client
from utils import normalize_comment_text, loose_comment_key

PAGE = 1000  # PostgREST の最大返却件数。全件処理するため id 昇順でページングする。


def fetch_all(sb, table, columns):
    rows = []
    start = 0
    while True:
        chunk = (sb.table(table).select(columns)
                 .order('id').range(start, start + PAGE - 1).execute().data) or []
        rows.extend(chunk)
        if len(chunk) < PAGE:
            break
        start += PAGE
    return rows


def player_ref(r):
    return (
        r.get('player_id')
        or ('cand:' + r['player_candidate_id'] if r.get('player_candidate_id') else None)
        or ('name:' + (r.get('player_name') or ''))
    )


def survivor_order(r):
    # 代表選定の昇順キー: 長文(loose長)を優先 → scout_name有 → 非yahoo → created_at古い順。
    src = r.get('source_url') or ''
    return (
        -len(loose_comment_key(r.get('comment'))),
        0 if (r.get('scout_name') or '').strip() else 1,
        1 if 'news.yahoo.co.jp' in src else 0,
        r.get('created_at') or '',
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='実際に更新・削除する（既定はdry-run）')
    args = ap.parse_args()

    ok, sb = _init_supabase_client()
    if sb is None:
        print('Supabase未接続'); return

    rows = fetch_all(
        sb, 'scout_comments',
        'id,comment,scout_name,team_name,player_name,player_id,player_candidate_id,source_url,created_at',
    )

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'=== scout_comments 正規化＋重複統合 [{mode}] ===')
    print(f'総コメント {len(rows)} 件\n')

    # (1) 鉤括弧除去などの正規化対象を抽出
    to_normalize = []
    for r in rows:
        norm = normalize_comment_text(r.get('comment'))
        if norm != (r.get('comment') or ''):
            to_normalize.append((r, norm))
    print(f'[1] 表記正規化（「」除去・空白整理）対象: {len(to_normalize)} 件')
    for r, norm in to_normalize[:5]:
        print(f'    {r["id"][:8]}: {(r.get("comment") or "")[:30]!r} → {norm[:30]!r}')
    if len(to_normalize) > 5:
        print(f'    … 他 {len(to_normalize) - 5} 件')

    # (2) 重複統合（同一選手×緩いキー完全一致＝句読点・記号・空白を無視した一致のみ）。
    # 部分一致は長文評価の別文や別スカウト発言を誤統合するため採用しない。
    groups = defaultdict(list)
    for r in rows:
        lk = loose_comment_key(r.get('comment'))
        if not lk:
            continue
        groups[(player_ref(r), lk)].append(r)
    dup_clusters = []  # [(pref, [survivor, loser...]), ...]
    for (pref, _lk), group in groups.items():
        if len(group) > 1:
            ordered = sorted(group, key=survivor_order)  # survivorを先頭に
            dup_clusters.append((pref, ordered))

    del_total = sum(len(m) - 1 for _, m in dup_clusters)
    print(f'\n[2] 重複クラスタ: {len(dup_clusters)} 件 / 削除対象: {del_total} 件')
    for pref, members in dup_clusters:
        survivor = members[0]  # cluster_comments は survivor を先頭に置く
        losers = members[1:]
        print(f'    ■ pid={str(pref)[:12]} "{normalize_comment_text(survivor.get("comment"))[:34]}"')
        print(f'        keep {survivor["id"][:8]} (scout={survivor.get("scout_name") or "-"}, '
              f'{(survivor.get("source_url") or "")[:30]}, {len(survivor.get("comment") or "")}字)')
        for l in losers:
            print(f'        - del {l["id"][:8]} (scout={l.get("scout_name") or "-"}, '
                  f'{(l.get("source_url") or "")[:30]}, {len(l.get("comment") or "")}字)')

    if args.apply:
        # 先に重複削除 → 残ったsurvivorを正規化、の順で実行
        del_ids = set()
        for _, members in dup_clusters:
            for l in members[1:]:
                del_ids.add(l['id'])
        for cid in del_ids:
            sb.table('scout_comments').delete().eq('id', cid).execute()
        norm_done = 0
        for r, norm in to_normalize:
            if r['id'] in del_ids:
                continue
            sb.table('scout_comments').update({'comment': norm}).eq('id', r['id']).execute()
            norm_done += 1
        print(f'\n✅ 実行完了: 削除 {len(del_ids)} 件 / 正規化更新 {norm_done} 件 '
              f'（{len(rows)} → {len(rows) - len(del_ids)} 件）')
    else:
        print('\n（dry-run。--apply で実行）')


if __name__ == '__main__':
    main()
