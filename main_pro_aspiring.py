"""
プロ志望届 追跡バッチ（3時間ごと・ドラフト会議まで）

やること:
  1. 高野連・全日本大学野球連盟のプロ志望届名簿を全件取得
  2. players と名寄せ（旧字体・異体字・ふりがな・学校名の表記ゆれを吸収）
  3. 登録済み選手は declared=false なら true に更新し、記事に紐付ける
  4. Draft-Watch記事候補「{year}年プロ志望届 提出者一覧」1本を毎回作り直して上書き
  5. 未登録・同名複数でどの選手か決められない選手を、GitHubのトラッカーIssue1本にまとめる

使い方:
  PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py                # 通常実行
  PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --dry-run      # DB・Issueに書かずに結果だけ表示
  PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --no-issues    # Issueだけ触らない
  PYTHONPATH=. venv/bin/python3 main_pro_aspiring.py --force        # 実行期間外でも走らせる
"""

import argparse
import json
import re
from datetime import date
from typing import Any, Dict, List, Optional

from database.player_matcher import MatchResult, PlayerMatcher, name_key, school_key
from database.pro_aspiring_store import ProAspiringStore
from database.supabase_client import now_jst
from integrations.github_issues import GitHubIssueClient
from pro_aspiring_article import build_excerpt, build_markdown, build_title
from scraper.pro_aspiring import fetch_all_pro_aspiring

DEFAULT_YEAR = 2026
# ドラフト会議（10月下旬）まで。これを過ぎたら名簿は動かないのでバッチは何もしない。
DEFAULT_UNTIL = '10-31'

TOPIC_KEY_TEMPLATE = 'other:pro_aspiring:{year}'
ISSUE_LABEL_TEMPLATE = 'pro-aspiring-{year}'
TRACKER_TITLE_TEMPLATE = '[志望届{year}] 未登録選手トラッカー'
TRACKER_MARKER = '<!-- pro-aspiring-tracker -->'
REVIEW_NOTE_MARKER = '<!-- pro-aspiring auto -->'

SOURCE_LINKS = [
    {'title': '日本高等学校野球連盟 プロ野球志望届提出者一覧',
     'url': 'https://www.jhbf.or.jp/pro-aspiring/{year}.html'},
    {'title': '全日本大学野球連盟 プロ野球志望届提出者',
     'url': 'https://www.jubf.net/system/prog/procandidate.php?kind=all&year={year}'},
]


def entry_key(entry: Dict[str, Any]) -> str:
    """名簿1行の同一性キー。表記ゆれで別人扱いにならないよう正規化キーで作る。"""
    return f"{entry.get('category')}|{name_key(entry.get('name'))}|{school_key(entry.get('school'))}"


def build_records(results: List[MatchResult], previous: Dict[str, Dict[str, Any]], now_iso: str) -> List[Dict[str, Any]]:
    """名簿エントリ＋名寄せ結果を、記事とsummary_jsonの両方で使うレコードにまとめる。"""
    records: List[Dict[str, Any]] = []
    for result in results:
        entry = result.entry
        key = entry_key(entry)
        prior = previous.get(key, {})
        player = result.player or {}
        records.append({
            'key': key,
            'category': entry.get('category'),
            'name': entry.get('name'),
            'name_kana': entry.get('name_kana'),
            'school': entry.get('school'),
            'affiliation': entry.get('affiliation'),
            'received_date': entry.get('received_date'),
            'draft_eligible': entry.get('draft_eligible', True),
            'source_url': entry.get('source_url'),
            'first_seen_at': prior.get('first_seen_at') or now_iso,
            'match_status': result.status,
            'matched_by': result.matched_by,
            'player_id': player.get('id'),
            'player_name': player.get('name'),
            'player_team': player.get('team'),
            'player_draft_year': player.get('draft_year'),
            'player_declared': player.get('declared'),
            'warnings': result.warnings,
            'suggestions': result.suggestions,
            'ambiguous_candidates': [
                {'id': c.get('id'), 'name': c.get('name'), 'team': c.get('team'),
                 'draft_year': c.get('draft_year')}
                for c in (result.candidates if result.status == 'ambiguous' else [])
            ],
        })
    return records


def _record_line(record: Dict[str, Any], checked: bool) -> str:
    """
    トラッカーIssueのチェックリスト1行。
    行末に不可視のキーコメントを埋めて、本文を書き換えてもチェック状態を引き継げるようにする。
    """
    parts = [f"{record.get('school')}／{record.get('affiliation')}"]
    if record.get('received_date'):
        parts.append(record['received_date'])
    if record.get('name_kana'):
        parts.append(record['name_kana'])
    if not record.get('draft_eligible'):
        parts.append('ドラフト対象外')

    line = f"- [{'x' if checked else ' '}] {record['name']}（{'・'.join(parts)}）"

    if record['match_status'] == 'ambiguous':
        candidates = ', '.join(
            f"{c['name']}（{c['team']}／{c['draft_year']}年） `{c['id']}`"
            for c in record.get('ambiguous_candidates', [])
        )
        line += f" → 同名の登録選手: {candidates}"
    elif record.get('suggestions'):
        suggestions = ', '.join(
            f"{s['name']}（{s['team']}・類似度{s['similarity']}） `{s['id']}`"
            for s in record['suggestions']
        )
        line += f" → 表記ゆれの可能性: {suggestions}"

    return line + f" <!--k:{record['key']}-->"


def parse_checked_keys(body: Optional[str]) -> set:
    """Issue本文から、人がチェック済みにした行のキーを拾う。"""
    if not body:
        return set()
    return set(re.findall(r'- \[x\][^\n]*<!--k:([^>]+?)-->', body, re.IGNORECASE))


def build_tracker_body(records: List[Dict[str, Any]], year: int, counts: Dict[str, int],
                       checked_keys: set, source_links: List[Dict[str, str]]) -> str:
    pending = [r for r in records if r['match_status'] in ('unmatched', 'ambiguous')]
    high_school = [r for r in pending if r['category'] == 'high_school']
    university = [r for r in pending if r['category'] == 'university']
    ambiguous = [r for r in pending if r['match_status'] == 'ambiguous']

    lines = [
        TRACKER_MARKER,
        f"{year}年のプロ志望届に名前があるのに、Draft-Watchの `players` に見つからない選手のトラッカー。",
        '`main_pro_aspiring.py` が3時間ごとに本文を書き換える（チェック状態は引き継ぐ）。',
        '',
        f"**最終更新**: {now_jst().strftime('%Y-%m-%d %H:%M')} JST",
        f"名簿 {counts['high_school'] + counts['university'] + counts['university_ineligible']}人 / "
        f"登録済み {counts['matched']}人 / 未登録 {counts['unmatched']}人 / 判定保留 {counts['ambiguous']}人",
        '',
    ]

    if not pending:
        lines.append('現時点で未登録の選手はいない。')
    for label, group in (('高校', high_school), ('大学', university)):
        if not group:
            continue
        lines.append(f'## {label}（{len(group)}人）')
        lines.append('')
        lines.extend(_record_line(r, r['key'] in checked_keys) for r in group)
        lines.append('')

    if ambiguous:
        lines.append('※ 「同名の登録選手」が付いている行は、同姓同名が複数いて自動で紐付けられなかった選手。'
                     '正しい選手を確認して `players` 側の所属・ドラフト年を直すと次回から自動で一致する。')
        lines.append('')

    lines.extend([
        '## 対応手順',
        '',
        '1. 同一人物が既に登録済みでないか確認する（表記ゆれ・別所属で登録されている場合がある）',
        '2. 未登録なら Phase 6 の手順で登録する'
        '（`docs/phase6_player_promotion_design.md` / `output/promote_drafts/{candidate_id}.json`）',
        '3. 登録すると次回の実行で自動的にリストから消え、`declared` も true になる',
        '4. 表記ゆれで取りこぼしていた場合は `database/player_matcher.py` の `EXTRA_VARIANT_MAP` に追記する',
        '',
        '## 出典',
        '',
    ])
    lines.extend(f"- [{s['title']}]({s['url']})" for s in source_links)
    return '\n'.join(lines)


def build_tracker_comment(new_pending: List[Dict[str, Any]], resolved: List[Dict[str, Any]]) -> str:
    lines = [f"### 更新 {now_jst().strftime('%Y-%m-%d %H:%M')} JST", '']
    if new_pending:
        lines.append(f'**新しく未登録の選手を検知（{len(new_pending)}人）**')
        lines.append('')
        for record in new_pending:
            label = '高校' if record['category'] == 'high_school' else '大学'
            lines.append(
                f"- {record['name']}（{record.get('school')}／{label}・"
                f"{record.get('received_date') or '受付日不明'}）"
            )
        lines.append('')
    if resolved:
        lines.append(f'**登録済みになった選手（{len(resolved)}人）**')
        lines.append('')
        for record in resolved:
            lines.append(
                f"- {record['name']}（{record.get('school')}）→ "
                f"`/players/{record.get('player_draft_year')}/{record.get('player_id')}`"
            )
        lines.append('')
    return '\n'.join(lines).rstrip()


def build_review_note(records: List[Dict[str, Any]], existing_note: Optional[str]) -> str:
    """要確認事項の自動生成ブロック。人が書いた部分（マーカーより前）は残す。"""
    warned = [r for r in records if r.get('warnings')]
    ambiguous = [r for r in records if r['match_status'] == 'ambiguous']
    unmatched = [r for r in records if r['match_status'] == 'unmatched']

    lines = [REVIEW_NOTE_MARKER, f"自動更新: {now_jst().strftime('%Y-%m-%d %H:%M')}"]
    lines.append(f"未登録 {len(unmatched)}人 / 同名複数で判定保留 {len(ambiguous)}人 / 要確認の紐付け {len(warned)}件")
    for record in ambiguous:
        lines.append(f"- 判定保留: {record['name']}（{record['school']}）")
    for record in warned:
        lines.append(f"- {record['name']} → {record['player_name']}: " + ' / '.join(record['warnings']))

    auto_block = '\n'.join(lines)
    if existing_note and REVIEW_NOTE_MARKER in existing_note:
        human_part = existing_note.split(REVIEW_NOTE_MARKER)[0].rstrip()
        return f"{human_part}\n\n{auto_block}" if human_part else auto_block
    if existing_note:
        return f"{existing_note.rstrip()}\n\n{auto_block}"
    return auto_block


def sync_tracker_issue(
    records: List[Dict[str, Any]],
    previous_entries: Dict[str, Dict[str, Any]],
    year: int,
    counts: Dict[str, int],
    source_links: List[Dict[str, str]],
    previous_issue_number: Optional[int],
    dry_run: bool,
) -> Dict[str, Any]:
    """
    未登録・判定保留の選手を1本のトラッカーIssueで管理する。
    本文は毎回まるごと書き換え、増減はコメントで知らせる。
    """
    stats: Dict[str, Any] = {'issue_number': previous_issue_number, 'pending': 0,
                             'new_pending': 0, 'resolved': 0, 'action': 'skipped'}
    pending = [r for r in records if r['match_status'] in ('unmatched', 'ambiguous')]
    stats['pending'] = len(pending)

    label = ISSUE_LABEL_TEMPLATE.format(year=year)
    title = TRACKER_TITLE_TEMPLATE.format(year=year)
    client = GitHubIssueClient(dry_run=dry_run)

    # 前回の状態と比べて「新しく未登録になった選手」「登録されて解消した選手」を出す。
    def was_pending(key: str) -> bool:
        return (previous_entries.get(key) or {}).get('match_status') in ('unmatched', 'ambiguous')

    new_pending = [r for r in pending if previous_entries and not was_pending(r['key'])]
    resolved = [
        r for r in records
        if r['match_status'] == 'matched' and was_pending(r['key'])
    ]
    stats['new_pending'] = len(new_pending)
    stats['resolved'] = len(resolved)

    if dry_run:
        print('----- トラッカーIssue本文 -----')
        print(build_tracker_body(records, year, counts, set(), source_links))
        print('------------------------------')

    if not client.available:
        print("[GitHub] トークン/リポジトリを解決できないためIssue操作をスキップ "
              "（GH_TOKEN もしくは GITHUB_TOKEN を設定してください）")
        return stats

    issue = client.get_issue(previous_issue_number) if previous_issue_number else None
    if not issue:
        issue = client.find_issue_by_title(label, title)

    checked_keys = parse_checked_keys((issue or {}).get('body'))
    body = build_tracker_body(records, year, counts, checked_keys, source_links)

    if issue:
        stats['issue_number'] = issue.get('number')
        client.update_issue(issue['number'], body)
        stats['action'] = 'updated'
        if new_pending or resolved:
            client.create_comment(issue['number'], build_tracker_comment(new_pending, resolved))
    else:
        if not dry_run:
            client.ensure_label(label, color='0e8a16', description=f'{year}年プロ志望届の未登録選手')
        number = client.create_issue(title, body, [label])
        stats['issue_number'] = number
        stats['action'] = 'created'

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description='プロ志望届 追跡バッチ')
    parser.add_argument('--year', type=int, default=DEFAULT_YEAR, help='対象年（既定: 2026）')
    parser.add_argument('--dry-run', action='store_true', help='DB・GitHubに書き込まず結果だけ表示する')
    parser.add_argument('--no-issues', action='store_true', help='GitHub Issueを作成しない')
    parser.add_argument('--until', default=DEFAULT_UNTIL, help='実行期間の終わり（MM-DD、既定: 10-31）')
    parser.add_argument('--force', action='store_true', help='実行期間外でも実行する')
    parser.add_argument('--print-markdown', action='store_true', help='生成した記事本文を表示する')
    parser.add_argument('--no-publish-sync', action='store_true',
                        help='公開済み記事（articles）の本文を上書きしない（手で編集した公開記事を守りたいとき）')
    args = parser.parse_args()

    year = args.year
    today = now_jst().date()
    until_month, until_day = (int(v) for v in args.until.split('-'))
    if not args.force and today > date(year, until_month, until_day):
        print(f"=== プロ志望届バッチ: 実行期間（〜{year}-{args.until}）を過ぎているため終了 ===")
        return

    print(f"=== プロ志望届バッチ（{year}年） ===")

    entries = fetch_all_pro_aspiring(year)
    if not entries:
        print("[中断] 名簿を1件も取得できなかった。記事は更新しない（サイト側の障害・改修の可能性）。")
        return

    store = ProAspiringStore()
    players = store.load_players()
    print(f"[名寄せ] players 読み込み: {len(players)}件")
    matcher = PlayerMatcher(players)
    results = [matcher.match(entry, draft_year=year) for entry in entries]

    topic_key = TOPIC_KEY_TEMPLATE.format(year=year)
    candidate = store.find_candidate(topic_key)
    previous_summary = (candidate or {}).get('summary_json') or {}
    if isinstance(previous_summary, str):
        previous_summary = json.loads(previous_summary)
    previous_entries = {e['key']: e for e in previous_summary.get('entries', []) if e.get('key')}

    updated_at = now_jst()
    records = build_records(results, previous_entries, updated_at.isoformat())
    new_records = [r for r in records if r['key'] not in previous_entries] if previous_entries else []

    matched = [r for r in records if r['match_status'] == 'matched']
    ambiguous = [r for r in records if r['match_status'] == 'ambiguous']
    unmatched = [r for r in records if r['match_status'] == 'unmatched']

    print(f"[名寄せ] 名簿 {len(records)}人 → 登録済み {len(matched)}人 / "
          f"未登録 {len(unmatched)}人 / 判定保留 {len(ambiguous)}人")
    for record in matched:
        note = f"（{' / '.join(record['warnings'])}）" if record['warnings'] else ''
        print(f"  ○ {record['name']}（{record['school']}） → {record['player_name']} "
              f"[{record['matched_by']}]{note}")
    for record in ambiguous:
        names = ' / '.join(f"{c['name']}（{c['team']}）" for c in record['ambiguous_candidates'])
        print(f"  ? {record['name']}（{record['school']}） → 候補複数: {names}")
    for record in unmatched:
        hint = ''
        if record['suggestions']:
            hint = ' / 似ている登録選手: ' + ', '.join(
                f"{s['name']}（{s['team']}・{s['similarity']}）" for s in record['suggestions']
            )
        print(f"  × {record['name']}（{record['school']}） 未登録{hint}")

    # 1. declared の更新（志望届提出＝プロ志望表明）
    declared_targets = [r for r in matched if r['player_id'] and not r.get('player_declared')]
    if declared_targets:
        print(f"\n[declared] false → true に更新: {len(declared_targets)}人")
        for record in declared_targets:
            print(f"  - {record['player_name']}（{record['player_team']}）")
    if declared_targets and not args.dry_run:
        updated = store.set_declared([r['player_id'] for r in declared_targets])
        print(f"[declared] 更新: {updated}件")

    counts = {
        'high_school': sum(1 for r in records if r['category'] == 'high_school'),
        'university': sum(1 for r in records if r['category'] == 'university' and r['draft_eligible']),
        'university_ineligible': sum(1 for r in records if r['category'] == 'university' and not r['draft_eligible']),
        'matched': len(matched),
        'unmatched': len(unmatched),
        'ambiguous': len(ambiguous),
    }
    source_links = [{'title': s['title'], 'url': s['url'].format(year=year)} for s in SOURCE_LINKS]

    # 2. GitHubトラッカーIssue（Issue番号をsummary_jsonへ残すので記事更新より先に実行する）
    if args.no_issues:
        issue_stats = {'issue_number': previous_summary.get('github_issue_number'),
                       'pending': len(unmatched) + len(ambiguous), 'new_pending': 0,
                       'resolved': 0, 'action': 'skipped'}
        print("\n[GitHub] --no-issues のためIssueは触らない")
    else:
        print()
        issue_stats = sync_tracker_issue(
            records, previous_entries, year, counts, source_links,
            previous_summary.get('github_issue_number'), args.dry_run,
        )
        print(f"[GitHub] トラッカーIssue: {issue_stats['action']} "
              f"(#{issue_stats['issue_number']}) / 未登録・保留 {issue_stats['pending']}人 / "
              f"新規 {issue_stats['new_pending']}人 / 解消 {issue_stats['resolved']}人")

    # 3. 記事本文の組み立て
    title = build_title(year, counts)
    markdown = build_markdown(year, records, counts, updated_at, new_records, source_links)
    excerpt = build_excerpt(year, counts, updated_at)

    summary_json = {
        'type': 'pro_aspiring_roster',
        'year': year,
        'updated_at': updated_at.isoformat(),
        'counts': counts,
        'sources': source_links,
        'entries': records,
        'linked_player_ids': [r['player_id'] for r in matched if r['player_id']],
        'declared_updated': [
            {'player_id': r['player_id'], 'name': r['player_name']} for r in declared_targets
        ],
        'github_issue_number': issue_stats.get('issue_number'),
    }

    if args.print_markdown or args.dry_run:
        print('\n----- 記事本文 -----')
        print(markdown)
        print('--------------------')

    if args.dry_run:
        print(f"[dry-run] 記事タイトル: {title}")
        print("[dry-run] DBへの書き込みは行わなかった。")
        return

    # 4. Draft-Watch記事候補の作成/更新
    review_note = build_review_note(records, (candidate or {}).get('review_note'))
    fields = {
        'title': title,
        'summary_json': summary_json,
        'draft_article_markdown': markdown,
        'draft_article_excerpt': excerpt,
        'source_urls': [s['url'] for s in source_links],
        'review_note': review_note,
        'updated_at': updated_at.isoformat(),
    }

    if candidate:
        store.update_candidate(candidate['id'], fields)
        candidate_id = candidate['id']
        published_article_id = candidate.get('published_article_id')
        print(f"\n[記事] 既存候補を更新: {candidate_id}（status={candidate.get('status')}）")
    else:
        record = {
            'topic_key': topic_key,
            'topic_type': 'other',
            'main_player_id': None,
            'main_player_name': None,
            'importance_score': 5,
            'status': 'draft',
            **fields,
        }
        created = store.insert_candidate(record)
        if not created:
            print("[エラー] 記事候補の作成に失敗した。")
            return
        candidate_id = created['id']
        published_article_id = None
        print(f"\n[記事] 新規候補を作成: {candidate_id}")

    store.add_sources(candidate_id, [s['url'] for s in source_links])

    # 5. 公開済みなら公開記事側も同期し、登場選手を紐付ける
    if published_article_id:
        if args.no_publish_sync:
            print(f"[記事] --no-publish-sync のため公開記事の本文は更新しない（{published_article_id}）")
        else:
            synced = store.sync_published_article(published_article_id, title, markdown, excerpt)
            print(f"[記事] 公開記事の同期: {'完了' if synced else '失敗'}（{published_article_id}）")
        linked = store.sync_article_players(published_article_id, summary_json['linked_player_ids'])
        print(f"[記事] 選手の紐付け追加: {linked}件")
    else:
        print("[記事] 未公開のため article_players の紐付けは公開後に行う"
              f"（紐付け対象 {len(summary_json['linked_player_ids'])}人は summary_json に記録済み）")

    print("\n=== 完了 ===")
    print(f"名簿 {len(records)}人 / 登録済み {len(matched)}人 / 未登録 {len(unmatched)}人 / "
          f"判定保留 {len(ambiguous)}人 / 新規提出 {len(new_records)}人 / "
          f"トラッカーIssue #{issue_stats.get('issue_number')}")


if __name__ == '__main__':
    main()
