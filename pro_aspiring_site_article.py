"""
公開記事（articles）側の「日々更新される部分」だけを差し替える。

公開記事は人が書いた解説・リード・注記を含むので、本文をまるごと上書きしない。
見出しを目印にして、その直後の表と、人数・日付を書いた定型文だけを機械が書き換える。
目印の見出しが見つからないブロックは**何もせずスキップ**する（人が構成を変えたときに壊さない）。

機械が書き換えるのは以下だけ:
  1. リードの「N月N日時点の提出者は高校生N人・大学生N人の合計N人」
  2. 「## 高校生の…提出者一覧（N人）」の見出しの人数と、直後の表
  3. 「## 大学生の…提出者一覧（N人）」の見出しの人数と、直後の表
  4. 「## まだ提出していない…」の「N月N日時点で一覧に名前が無い高校生はN人、大学生はN人です」
  5. 同セクションの「### 高校生」「### 大学生」直後の表
  6. タイトル・抜粋・メタディスクリプション内の日付と人数
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

SITE_ORIGIN = 'https://draft-watch.com'
PLAYER_URL = SITE_ORIGIN + '/players/{draft_year}/{player_id}'

# players.rank（int）→ 編集部評価ラベル。draft-watch の lib/utils.ts getRankLabel と揃える。
RANK_LABELS = {90: 'S', 80: 'A', 70: 'B', 60: 'C', 50: 'D', 40: 'E', 30: 'F'}
# 「上位候補」とみなす下限（B以上）
PENDING_RANK_MIN = 70
PENDING_TABLE_LIMIT = 10

EMPTY = '—'

# 見出しの目印。人が言い回しを変えても拾えるよう、キーワードだけで緩く当てる。
HEADING_HIGH_SCHOOL = re.compile(r'^##\s+.*高校生.*一覧.*$', re.MULTILINE)
HEADING_UNIVERSITY = re.compile(r'^##\s+.*大学生.*一覧.*$', re.MULTILINE)
HEADING_PENDING = re.compile(r'^##\s+.*まだ提出していない.*$', re.MULTILINE)
SUBHEADING_HIGH_SCHOOL = re.compile(r'^###\s+高校生.*$', re.MULTILINE)
SUBHEADING_UNIVERSITY = re.compile(r'^###\s+大学生.*$', re.MULTILINE)

# 人数・日付を含む定型文
LEAD_SENTENCE = re.compile(
    r'\*\*\d+月\d+日時点の提出者は高校生\d+人・大学生\d+人の合計\d+人\*\*'
)
PENDING_SENTENCE = re.compile(
    r'\d+月\d+日時点で一覧に名前が無い高校生は\d+人、大学生は\d+人です'
)
# 注記の「（2026年9月3日午後5時時点）」＝名簿ページを読んだ時刻
SOURCE_TIMESTAMP = re.compile(r'（20\d\d年\d+月\d+日[^）]*時点）')
TITLE_DATE = re.compile(r'（\d+月\d+日時点）')
TITLE_COUNTS = re.compile(r'高校生\d+人・大学生\d+人')
EXCERPT_DATE_COUNTS = re.compile(r'\d+月\d+日時点は高校生\d+人・大学生\d+人の計\d+人')


def rank_label(rank: Optional[int]) -> str:
    return RANK_LABELS.get(rank or 0, EMPTY)


def position_label(position: Any) -> str:
    if not position:
        return EMPTY
    if isinstance(position, str):
        return position
    return '・'.join(str(p) for p in position if p) or EMPTY


def player_link(name: str, player_id: Optional[str], draft_year: Optional[int], year: int) -> str:
    if not player_id:
        return name
    return f"[{name}]({PLAYER_URL.format(draft_year=draft_year or year, player_id=player_id)})"


def federation_label(affiliation: Optional[str]) -> str:
    """「東都大学野球連盟」→「東都大学」。記事の表記に合わせて連盟の語を落とす。"""
    if not affiliation:
        return EMPTY
    return re.sub(r'(野球)?連盟$', '', affiliation) or affiliation


def _table(header: List[str], rows: List[List[str]]) -> str:
    lines = ['| ' + ' | '.join(header) + ' |',
             '|' + '|'.join(['---'] * len(header)) + '|']
    lines.extend('| ' + ' | '.join(row) + ' |' for row in rows)
    return '\n'.join(lines)


def build_roster_table(records: List[Dict[str, Any]], category: str, year: int,
                       players_by_id: Dict[str, Dict[str, Any]]) -> str:
    """
    提出者一覧の表。並びは連盟の公表順（スクレイプ順）のまま。
    ポジション・評価は players から引く（未登録選手は「—」）。
    """
    is_high_school = category == 'high_school'
    header = (['都道府県', '学校', '選手', 'ポジション', '評価', '受付日'] if is_high_school
              else ['連盟', '大学', '選手', 'ポジション', '評価', '受付日'])

    rows: List[List[str]] = []
    for record in records:
        if record.get('category') != category:
            continue
        player = players_by_id.get(record.get('player_id') or '') or {}
        rows.append([
            record.get('affiliation') or EMPTY if is_high_school
            else federation_label(record.get('affiliation')),
            record.get('school') or EMPTY,
            player_link(record.get('name') or '', record.get('player_id'),
                        player.get('draft_year'), year),
            position_label(player.get('position')),
            rank_label(player.get('rank')),
            record.get('received_date') or EMPTY,
        ])
    return _table(header, rows)


def select_pending_players(players: List[Dict[str, Any]], submitted_ids: set, year: int,
                           category: str) -> List[Dict[str, Any]]:
    """志望届にまだ名前が無い、B以上の評価が付いた選手（評価の高い順）。"""
    pending = [
        p for p in players
        if p.get('draft_year') == year
        and p.get('category') == category
        and (p.get('rank') or 0) >= PENDING_RANK_MIN
        and p.get('id') not in submitted_ids
    ]
    pending.sort(key=lambda p: (-(p.get('rank') or 0), p.get('name') or ''))
    return pending


def build_pending_table(pending: List[Dict[str, Any]], year: int,
                        limit: int = PENDING_TABLE_LIMIT) -> str:
    rows = [
        [
            rank_label(player.get('rank')),
            player_link(player.get('name') or '', player.get('id'), player.get('draft_year'), year),
            player.get('team') or EMPTY,
            position_label(player.get('position')),
        ]
        for player in pending[:limit]
    ]
    return _table(['評価', '選手', '所属', 'ポジション'], rows)


def _replace_table_after(content: str, anchor_end: int, table: str) -> Tuple[str, bool]:
    """
    anchor_end 以降の最初の表（連続する `|` 行）を table に差し替える。
    表が見つからなければ何もしない。
    """
    lines = content.split('\n')
    # 文字位置 → 行番号（見出し行の次の行から探す）
    offset = 0
    start_line = None
    for index, line in enumerate(lines):
        offset += len(line) + 1
        if offset > anchor_end:
            start_line = index + 1
            break
    if start_line is None or start_line >= len(lines):
        return content, False

    table_start = None
    for index in range(start_line, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith('|'):
            table_start = index
            break
        # 次の見出しに当たったら、このセクションに表は無い
        if stripped.startswith('#'):
            return content, False
    if table_start is None:
        return content, False

    table_end = table_start
    while table_end < len(lines) and lines[table_end].strip().startswith('|'):
        table_end += 1

    lines[table_start:table_end] = table.split('\n')
    return '\n'.join(lines), True


def _update_heading_count(content: str, pattern: re.Pattern, count: int) -> Tuple[str, bool]:
    """見出しの「（N人）」を更新する。"""
    match = pattern.search(content)
    if not match:
        return content, False
    heading = match.group(0)
    updated = re.sub(r'（\d+人）', f'（{count}人）', heading)
    if updated == heading:
        return content, False
    return content[:match.start()] + updated + content[match.end():], True


def update_article_content(
    content: str,
    records: List[Dict[str, Any]],
    players: List[Dict[str, Any]],
    year: int,
    updated_at: datetime,
    counts: Dict[str, int],
) -> Tuple[str, List[str]]:
    """
    公開記事の本文のうち、機械が持っているブロックだけを差し替える。
    返り値は (新しい本文, 更新できたブロック名のログ)。
    """
    players_by_id = {p['id']: p for p in players}
    submitted_ids = {r['player_id'] for r in records if r.get('player_id')}
    date_label = f"{updated_at.month}月{updated_at.day}日"
    updated_blocks: List[str] = []

    high_school_count = counts['high_school']
    university_count = counts['university'] + counts['university_ineligible']
    total = high_school_count + university_count

    # 1. リードの人数
    new_content, hit = _sub_once(
        content, LEAD_SENTENCE,
        f"**{date_label}時点の提出者は高校生{high_school_count}人・"
        f"大学生{university_count}人の合計{total}人**",
    )
    content = new_content
    if hit:
        updated_blocks.append('リード文の人数')

    # 1.5. 注記の「◯◯時点」＝名簿ページを読んだ時刻
    content, hit = _sub_once(
        content, SOURCE_TIMESTAMP,
        f"（{updated_at.year}年{updated_at.month}月{updated_at.day}日"
        f"{updated_at.hour}時{updated_at.minute:02d}分時点）",
    )
    if hit:
        updated_blocks.append('注記の時点')

    # 2-3. 提出者一覧（見出しの人数＋表）
    for label, heading, category, count in (
        ('高校生一覧', HEADING_HIGH_SCHOOL, 'high_school', high_school_count),
        ('大学生一覧', HEADING_UNIVERSITY, 'university', university_count),
    ):
        content, heading_hit = _update_heading_count(content, heading, count)
        match = heading.search(content)
        if not match:
            print(f"[記事] 見出しが見つからないためスキップ: {label}")
            continue
        table = build_roster_table(records, category, year, players_by_id)
        content, table_hit = _replace_table_after(content, match.end(), table)
        if table_hit or heading_hit:
            updated_blocks.append(label)
        if not table_hit:
            print(f"[記事] 表が見つからないためスキップ: {label}")

    # 4-5. まだ提出していない上位候補
    pending_match = HEADING_PENDING.search(content)
    if pending_match:
        pending_high_school = select_pending_players(players, submitted_ids, year, 'high_school')
        pending_university = select_pending_players(players, submitted_ids, year, 'university')

        content, hit = _sub_once(
            content, PENDING_SENTENCE,
            f"{date_label}時点で一覧に名前が無い高校生は{len(pending_high_school)}人、"
            f"大学生は{len(pending_university)}人です",
        )
        if hit:
            updated_blocks.append('未提出の人数')

        section_start = pending_match.end()
        for label, subheading, pending in (
            ('未提出（高校生）', SUBHEADING_HIGH_SCHOOL, pending_high_school),
            ('未提出（大学生）', SUBHEADING_UNIVERSITY, pending_university),
        ):
            sub_match = subheading.search(content, section_start)
            if not sub_match:
                print(f"[記事] 見出しが見つからないためスキップ: {label}")
                continue
            content, table_hit = _replace_table_after(
                content, sub_match.end(), build_pending_table(pending, year))
            if table_hit:
                updated_blocks.append(label)
    else:
        print("[記事] 「まだ提出していない主な上位候補」の見出しが無いためスキップ")

    return content, updated_blocks


def _sub_once(content: str, pattern: re.Pattern, replacement: str) -> Tuple[str, bool]:
    if not pattern.search(content):
        return content, False
    return pattern.sub(lambda _match: replacement, content, count=1), True


def update_article_meta(article: Dict[str, Any], counts: Dict[str, int],
                        updated_at: datetime) -> Dict[str, str]:
    """
    タイトル・抜粋・メタディスクリプションの日付と人数だけを書き換える。
    人が書いた見出し文・選手名はそのまま残す。
    """
    date_label = f"{updated_at.month}月{updated_at.day}日"
    high_school_count = counts['high_school']
    university_count = counts['university'] + counts['university_ineligible']
    total = high_school_count + university_count

    fields: Dict[str, str] = {}
    for key in ('title', 'excerpt', 'meta_description'):
        original = article.get(key) or ''
        if not original:
            continue
        updated = TITLE_DATE.sub(f'（{date_label}時点）', original)
        updated = TITLE_COUNTS.sub(f'高校生{high_school_count}人・大学生{university_count}人', updated)
        updated = EXCERPT_DATE_COUNTS.sub(
            f"{date_label}時点は高校生{high_school_count}人・大学生{university_count}人の計{total}人",
            updated,
        )
        if updated != original:
            fields[key] = updated
    return fields
