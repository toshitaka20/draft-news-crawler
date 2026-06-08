"""
Draft-Watch記事候補生成バッチ
1日1回、朝の時間帯に実行する（main_regular.py / main_yahoo_sponavi.py とは独立）。

前回実行以降に attention_signals へ蓄積された新着シグナルを対象に、
トピック判定（topic_key一致 → ルールベース近傍判定）でトピックへ合流させるか新規候補を作成し、
summary_json / importance_score を更新したうえで、閾値を超えた候補だけ下書き記事をAI生成する。

オプション:
  （引数なし）            : 通常モード。前回以降の新着シグナルを処理する。
  --regenerate           : 既存のdraft候補すべての summary_json / 下書き本文を作り直す
                           （プロンプト改善を既存候補へ反映したいとき）。
  --regenerate-missing   : 本文が未生成のdraft候補だけを対象に下書きを生成する。
"""

import argparse

from database.supabase_client import (
    process_draft_watch_candidates,
    regenerate_draft_watch_drafts,
)


def _print_results(results):
    print("\n=== 処理結果 ===")
    print(f"対象シグナル数: {results['signals']}件")
    print(f"新規トピック作成: {results['candidates_created']}件")
    print(f"既存トピックへ合流/再生成: {results['candidates_updated']}件")
    print(f"下書き記事生成: {results['drafts_generated']}件")
    print(f"エラー件数: {results['errors']}件")


def main():
    parser = argparse.ArgumentParser(description="Draft-Watch記事候補生成バッチ")
    parser.add_argument(
        '--regenerate',
        action='store_true',
        help='既存のdraft候補すべての下書きを作り直す（プロンプト改善の反映用）',
    )
    parser.add_argument(
        '--regenerate-missing',
        action='store_true',
        help='本文が未生成のdraft候補だけを対象に下書きを生成する',
    )
    args = parser.parse_args()

    regenerate = args.regenerate or args.regenerate_missing

    if regenerate:
        only_missing = args.regenerate_missing and not args.regenerate
        mode = "本文未生成のみ" if only_missing else "全draft候補"
        print(f"=== Draft-Watch下書き再生成バッチ（対象: {mode}）===")
    else:
        print("=== Draft-Watch記事候補生成バッチ ===")

    try:
        if regenerate:
            only_missing = args.regenerate_missing and not args.regenerate
            results = regenerate_draft_watch_drafts(only_missing=only_missing)
        else:
            results = process_draft_watch_candidates()

        _print_results(results)

    except Exception as e:
        print(f"[エラー] Draft-Watchバッチ失敗: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
