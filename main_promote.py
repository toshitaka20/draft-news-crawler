"""
選手候補のリサーチ付き昇格バッチ（Phase 6）。

当面は CLI だけで「候補選択 → リサーチ → 本テーブル登録」を完結させる運用。
リサーチ・昇格案JSON作成は Claude Code が担当し、本CLIは候補一覧・取り込み・昇格を担う。
（アプリ=draft-watch からの workflow_dispatch 起動の設計も docs に残してある。）

詳細設計: docs/phase6_player_promotion_design.md

使い方:
  # 1) 候補を選ぶ（pending一覧。--status all で全件）
  python main_promote.py --mode list
  python main_promote.py --mode list --status all

  # 2) Claude Code がリサーチして output/promote_drafts/{candidate_id}.json を作成

  # 3) 取り込み＋昇格を一発で（推奨）
  python main_promote.py --mode promote --file output/promote_drafts/xxx.json

  # （分割実行したい場合）
  python main_promote.py --mode import-draft --file output/promote_drafts/xxx.json
  python main_promote.py --mode commit --candidate-ids "id1,id2"
"""

import argparse
import json

from database.supabase_client import (
    import_player_promotion_draft,
    commit_player_promotions,
    list_promotion_candidates,
    promote_player_from_draft,
)


def _run_list(status: str):
    rows = list_promotion_candidates(status=status)
    print(f"=== 候補一覧 (status={status}): {len(rows)}件 ===")
    for r in rows:
        flag = ' [昇格済]' if r.get('player_id') else ''
        print(
            f"{r['id']}  {r.get('name')}"
            f"（{r.get('team')} / {r.get('category')} / {r.get('draft_year')}）"
            f" research={r.get('research_status')}{flag}"
        )


def _run_import(path: str):
    with open(path, encoding='utf-8') as f:
        payload = json.load(f)
    ok = import_player_promotion_draft(payload)
    print("結果:", "成功" if ok else "失敗/スキップ")


def _run_commit(candidate_ids):
    results = commit_player_promotions(candidate_ids)
    print("\n=== 処理結果 ===")
    print(f"昇格: {results['committed']}件 / スキップ: {results['skipped']}件 / エラー: {results['errors']}件")


def _run_promote(path: str):
    with open(path, encoding='utf-8') as f:
        payload = json.load(f)
    player_id = promote_player_from_draft(payload)
    if player_id:
        print(f"✅ 昇格完了 → player_id={player_id}")
    else:
        print("失敗/スキップ（candidate_id や research_payload を確認してください）")


def main():
    parser = argparse.ArgumentParser(description="選手候補のリサーチ付き昇格バッチ（Phase 6）")
    parser.add_argument('--mode', required=True, choices=['list', 'import-draft', 'commit', 'promote'])
    parser.add_argument('--file', help='import-draft / promote: 昇格案JSONファイルのパス')
    parser.add_argument('--candidate-ids', help='commit: カンマ区切りの候補UUID')
    parser.add_argument('--status', default='pending', help='list: 絞り込むstatus（既定 pending、all で全件）')
    args = parser.parse_args()

    if args.mode == 'list':
        _run_list(args.status)

    elif args.mode == 'import-draft':
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

    elif args.mode == 'promote':
        if not args.file:
            parser.error('--mode promote には --file が必要です')
        print(f"=== 一気通貫昇格（import+commit）: {args.file} ===")
        _run_promote(args.file)


if __name__ == '__main__':
    main()
