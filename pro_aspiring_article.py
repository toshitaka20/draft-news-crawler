"""
プロ志望届まとめ記事（Draft-Watch）の本文組み立て。

名簿は提出があるたびに増えていくので、記事は毎回まるごと作り直して同じ候補行を上書きする。
AI生成はせず、名簿の内容をそのまま構造化して出す（数字と氏名が命の記事なので創作の余地を作らない）。
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

SITE_PLAYER_PATH = '/players/{draft_year}/{player_id}'

CATEGORY_LABEL = {
    'high_school': '高校',
    'university': '大学',
}


def parse_received_date(text: Optional[str]) -> Optional[Tuple[int, int]]:
    """「8月25日」→ (8, 25)。パースできなければ None。"""
    if not text:
        return None
    match = re.search(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _sort_key(record: Dict[str, Any], year: int) -> Tuple:
    """受付日の新しい順 → 学校名 → 氏名。受付日不明は最後に回す。"""
    parsed = parse_received_date(record.get('received_date'))
    month, day = parsed if parsed else (0, 0)
    return (-month, -day, record.get('school') or '', record.get('name') or '')


def _player_link(record: Dict[str, Any], year: int) -> str:
    """登録済み選手は選手ページへのリンク、未登録は氏名のみ。"""
    name = record.get('name') or ''
    player_id = record.get('player_id')
    if not player_id:
        return name
    draft_year = record.get('player_draft_year') or year
    return f"[{name}]({SITE_PLAYER_PATH.format(draft_year=draft_year, player_id=player_id)})"


def _table(records: List[Dict[str, Any]], year: int, with_kana: bool) -> List[str]:
    if with_kana:
        lines = ['| 受付日 | 連盟 | 大学 | 選手 | ふりがな | Draft-Watch |',
                 '|---|---|---|---|---|---|']
    else:
        lines = ['| 受付日 | 都道府県 | 学校 | 選手 | Draft-Watch |',
                 '|---|---|---|---|---|']

    for record in sorted(records, key=lambda r: _sort_key(r, year)):
        registered = '登録済み' if record.get('player_id') else '—'
        cells = [
            record.get('received_date') or '—',
            record.get('affiliation') or '—',
            record.get('school') or '—',
            _player_link(record, year),
        ]
        if with_kana:
            cells.append(record.get('name_kana') or '—')
        cells.append(registered)
        lines.append('| ' + ' | '.join(cells) + ' |')
    return lines


def build_title(year: int, counts: Dict[str, int]) -> str:
    return (
        f"【{year}年プロ志望届】提出者一覧 高校{counts.get('high_school', 0)}人・"
        f"大学{counts.get('university', 0)}人（随時更新）"
    )


def build_excerpt(year: int, counts: Dict[str, int], updated_at: datetime) -> str:
    return (
        f"{year}年のプロ野球志望届の提出者一覧。"
        f"{updated_at.strftime('%m月%d日')}時点で高校{counts.get('high_school', 0)}人、"
        f"大学{counts.get('university', 0)}人が提出。日本高野連・全日本大学野球連盟の公示をもとに"
        f"3時間ごとに自動更新している。"
    )


def build_markdown(
    year: int,
    records: List[Dict[str, Any]],
    counts: Dict[str, int],
    updated_at: datetime,
    new_records: List[Dict[str, Any]],
    source_urls: List[Dict[str, str]],
) -> str:
    high_school = [r for r in records if r.get('category') == 'high_school']
    university = [r for r in records if r.get('category') == 'university' and r.get('draft_eligible')]
    ineligible = [r for r in records if r.get('category') == 'university' and not r.get('draft_eligible')]
    registered = [r for r in records if r.get('player_id')]

    lines: List[str] = []
    lines.append(f"## {year}年 プロ志望届の提出状況")
    lines.append('')
    lines.append(f"{updated_at.strftime('%Y年%m月%d日 %H:%M')}時点の提出者は以下の通り。")
    lines.append('')
    lines.append(f"- 高校: **{len(high_school)}人**")
    lines.append(f"- 大学: **{len(university)}人**")
    if ineligible:
        lines.append(f"- 大学（NPBドラフト対象外）: {len(ineligible)}人")
    lines.append(f"- うちDraft-Watchに選手ページがある選手: {len(registered)}人")
    lines.append('')
    lines.append('日本高等学校野球連盟・全日本大学野球連盟の公示をもとに、3時間ごとに自動更新している。')
    lines.append('')

    if new_records:
        lines.append('## 前回更新からの新規提出者')
        lines.append('')
        for record in sorted(new_records, key=lambda r: _sort_key(r, year)):
            label = CATEGORY_LABEL.get(record.get('category', ''), '')
            lines.append(
                f"- {record.get('received_date') or '受付日不明'} "
                f"{_player_link(record, year)}（{record.get('school')}／{label}）"
            )
        lines.append('')

    if high_school:
        lines.append(f'## 高校（{len(high_school)}人）')
        lines.append('')
        lines.extend(_table(high_school, year, with_kana=False))
        lines.append('')

    if university:
        lines.append(f'## 大学（{len(university)}人）')
        lines.append('')
        lines.extend(_table(university, year, with_kana=True))
        lines.append('')

    if ineligible:
        lines.append(f'## 大学・NPBドラフト対象外（{len(ineligible)}人）')
        lines.append('')
        lines.append('志望届は提出しているが、今年のNPBドラフトの指名対象ではないと連盟が公示している選手。')
        lines.append('')
        lines.extend(_table(ineligible, year, with_kana=True))
        lines.append('')

    lines.append('## 出典')
    lines.append('')
    for source in source_urls:
        lines.append(f"- [{source['title']}]({source['url']})")
    lines.append('')

    return '\n'.join(lines).rstrip() + '\n'
