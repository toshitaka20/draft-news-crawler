"""
選手候補のリサーチ付き昇格バッチ（Phase 6）。

- import-draft : 昇格案JSON（output/promote_drafts/*.json）を player_candidates.research_payload に
                 取り込み、research_status='ready' にする。
- commit       : ready の候補を players / stats / player_achievements へ展開して昇格し、
                 promote_player_candidate_links() でリンクを伝播する。

詳細設計: docs/phase6_player_promotion_design.md

使い方:
  python main_promote.py --mode import-draft --file output/promote_drafts/xxx.json
  python main_promote.py --mode commit --candidate-ids "id1,id2"
"""

import argparse
import json

from database.supabase_client import (
    import_player_promotion_draft,
    commit_player_promotions,
)


def _run_import(path: str) -> bool:
    with open(path, encoding='utf-8') as f:
        payload = json.load(f)
    ok = import_player_promotion_draft(payload)
    print("結果:", "成功" if ok else "失敗/スキップ")
    return ok


def _run_commit(candidate_ids):
    results = commit_player_promotions(candidate_ids)
    print("\n=== 処理結果 ===")
    print(f"昇格: {results['committed']}件 / スキップ: {results['skipped']}件 / エラー: {results['errors']}件")


def main():
    parser = argparse.ArgumentParser(description="選手候補のリサーチ付き昇格バッチ（Phase 6）")
    parser.add_argument('--mode', required=True, choices=['import-draft', 'commit'])
    parser.add_argument('--file', help='import-draft: 昇格案JSONファイルのパス')
    parser.add_argument('--candidate-ids', help='commit: カンマ区切りの候補UUID')
    args = parser.parse_args()

    if args.mode == 'import-draft':
        if not args.file:
            parser.error('--mode import-draft には --file が必要です')
        print(f"=== 昇格案インポート: {args.file} ===")
        _run_import(args.file)

    elif args.mode == 'commit':
        ids = [x.strip() for x in (args.candidate_ids or '').split(',') if x.strip()]
        if not ids:
            parser.error('--mode commit には --candidate-ids が必要です')
        print(f"=== 昇格commit: {len(ids)}件 ===")
        _run_commit(ids)


if __name__ == '__main__':
    main()
