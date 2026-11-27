"""関西学生野球連盟（kansaibig6.jp）。

- シーズン個人成績（/{年}{spring|autumn}-kozinseiseki/）は規定打席・規定投球回の到達者だけ。
  フルネーム・学年・出身校つきで、四球・死球・犠飛・三振まで分かれている。
- 規定未満の選手は試合ごとのPDFしかないので、今は取り込まない（既存の行はそのまま残る）。
"""

import re
from typing import List, Optional

from database.player_matcher import school_key
from stats_sync.common import (
    BattingLine, ExtPlayer, PitchingLine, cell_text, fetch_html, parse_innings, soup_of, to_int,
)

SOURCE = 'kansai'
TOURNAMENT = '関西学生'
BASE = 'https://kansaibig6.jp/'

TEAMS = {'関大': '関西大', '関学大': '関西学院大', '京大': '京都大', '近大': '近畿大', '同大': '同志社大',
         '立命大': '立命館大'}


def page_url(year: int, season: str) -> str:
    return f'{BASE}{year}{"spring" if season == "spring" else "autumn"}-kozinseiseki/'


def is_existing_tournament(name: Optional[str]) -> bool:
    return (name or '').replace(' ', '').startswith('関西学生')


def canonical_team(abbr: str) -> str:
    abbr = abbr.strip()
    if abbr in TEAMS:
        return TEAMS[abbr]
    key = school_key(abbr)
    return next((v for v in TEAMS.values() if school_key(v) == key), abbr)


def fetch_season(year: int, season: str) -> List[ExtPlayer]:
    url = page_url(year, season)
    soup = soup_of(fetch_html(url))
    players = {}
    for table in soup.find_all('table'):
        rows = [[cell_text(c) for c in tr.find_all(['td', 'th'])] for tr in table.find_all('tr')]
        if not rows or rows[0][:3] != ['順位', 'チーム', '選手']:
            continue
        head = rows[0]
        col = lambda r, name: r[head.index(name)] if name in head else None  # noqa: E731
        is_pitch = '被安' in head
        for r in rows[1:]:
            if len(r) != len(head):
                continue
            team = canonical_team(r[1])
            full = re.sub(r'\s+', ' ', r[2]).strip()
            grade, _, hs = (r[3] or '').partition('・')
            key = f'{team}|{full}'
            ext = players.setdefault(key, ExtPlayer(
                source=SOURCE, ext_key=key, display_name=full, team=team, full_name=full,
                high_school=hs.strip() or None, profile_url=url,
                extra={'tournament': TOURNAMENT, 'grade': grade.strip()},
            ))
            if is_pitch:
                walks, hbp = to_int(col(r, '四球')), to_int(col(r, '死球'))
                ext.pitching = PitchingLine(
                    games=to_int(col(r, '試合')) or 0, wins=to_int(col(r, '勝')), losses=to_int(col(r, '負')),
                    batters_faced=to_int(col(r, '打者')), innings=parse_innings(col(r, '回')),
                    hits_allowed=to_int(col(r, '被安')), home_runs_allowed=to_int(col(r, '被本')),
                    walks=walks, hit_by_pitch=hbp,
                    walks_plus_hbp=(walks or 0) + (hbp or 0) if walks is not None else None,
                    strikeouts=to_int(col(r, '三振')), runs=to_int(col(r, '失点')),
                    earned_runs=to_int(col(r, '自責')),
                )
            else:
                ext.batting = BattingLine(
                    games=to_int(col(r, '試合')) or 0, plate_appearances=to_int(col(r, '打席')),
                    at_bats=to_int(col(r, '打数')) or 0, runs=to_int(col(r, '得点')),
                    hits=to_int(col(r, '安打')) or 0, doubles=to_int(col(r, '二打')),
                    triples=to_int(col(r, '三打')), home_runs=to_int(col(r, '本打')),
                    rbis=to_int(col(r, '打点')), steals=to_int(col(r, '盗塁')),
                    walks=to_int(col(r, '四球')), hit_by_pitch=to_int(col(r, '死球')),
                    sacrifice_flies=to_int(col(r, '犠飛')), strikeouts=to_int(col(r, '三振')),
                )
    return list(players.values())


def fill_profile(player: ExtPlayer) -> None:
    return None  # 表にフルネームが載っている


def source_url(ext: ExtPlayer, year: int, season: str) -> str:
    return page_url(year, season)
