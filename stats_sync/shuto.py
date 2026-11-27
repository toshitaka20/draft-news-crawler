"""首都大学野球連盟（tmubl.jp）。

- シーズン成績は上位10人のランキングだけなので、試合ごとの公式記録を足し上げる。
  各部のページ（/game/{年}{春|秋}?ds={年}{haru|aki}-{部}）に全試合の記録（div.match_data）が並んでいる。
  - 打撃: 打数・安打・打点（＋本塁打・三塁打・二塁打の一覧）。四死球・三振・盗塁・得点は載っていない
  - 投手: 投球回・打者数・被安打・自責（〇勝 ●負）。奪三振・四死球は載っていない
  載っていない項目は球歴.com の試合記録で補う（stats_sync/kyureki.py。公式と数字が一致した選手だけ）。
  補えなかった項目は null のまま入れる。
- 名前は「酒井成」のような略称（名字＋必要なら名の1文字）＋学年＋出身高校。フルネームは載っていないので、
  照合は「大学＋略称が名前の先頭と一致＋出身高校」で行う。
- 略称は大学の中で重ならないように付けられているので、足し上げは (大学, 略称) で1人とみなす
  （出身高校は試合によって「市立川口/川口市立」「二松學舍/二松學舎」と表記が揺れるため、キーに入れない）。
- 勝ち投手の印は「〇」「○」「◯」のどれも使われる。
"""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from database.player_matcher import name_key, school_key
from stats_sync.common import (
    BattingLine, ExtPlayer, PitchingLine, cell_text, fetch_html, parse_innings, soup_of, to_int,
)

SOURCE = 'shuto'
TOURNAMENT = '首都'
BASE = 'https://tmubl.jp/'
DIVISIONS = {'1': '首都1部', '2': '首都2部'}

# 加盟校（DB の大学名の表記）
UNIVS = ['筑波大', '日本体育大', '東海大', '帝京大', '武蔵大', '桜美林大', '東京経済大', '明星大', '獨協大',
         '城西大', '明治学院大', '日本ウェルネススポーツ大', '大東文化大', '足利大', '玉川大', '成城大']


def is_existing_tournament(name: Optional[str]) -> bool:
    return (name or '').replace(' ', '').startswith('首都')


def canonical_team(name: str) -> str:
    key = school_key(name)
    for u in UNIVS:
        if school_key(u) == key:
            return u
    return name.strip()


def division_url(year: int, season: str, division: str) -> str:
    term = '春' if season == 'spring' else '秋'
    code = 'haru' if season == 'spring' else 'aki'
    return f'{BASE}game/{year}{quote(term)}?ds={year}{code}-{division}'


def _table_rows(table) -> List[List[str]]:
    return [[cell_text(c) for c in tr.find_all(['td', 'th'])] for tr in table.find_all('tr')]


def _names_in(cell: str) -> List[str]:
    """「酒井成、藤巻、小上防」「大谷(1本)」→ 名前の一覧（(2本)なら2回数える）。"""
    out = []
    for part in re.split(r'[、,，・\s]+', cell or ''):
        part = part.strip()
        if not part or part in ('-', '－'):
            continue
        m = re.match(r'^(.*?)[(（](\d+)本?[)）]$', part)
        if m:
            out.extend([m.group(1).strip()] * int(m.group(2)))
        else:
            out.append(re.sub(r'[(（][^)）]*[)）]', '', part).strip())
    return [n for n in out if n]


@dataclass
class _Acc:
    team: str
    name: str
    grade: Optional[int]
    high_school: str
    bat: Optional[BattingLine] = None
    pit: Optional[PitchingLine] = None


def _parse_block(block, division: str, acc: Dict[Tuple[str, str], _Acc]) -> None:
    teams = [canonical_team(h.get_text(strip=True)) for h in block.select('h4.tit_02')]
    if len(teams) != 2:
        return
    xbh: Dict[str, Counter] = {t: Counter() for t in teams}   # team → Counter((name, kind))
    bat_tables, pit_tables = [], []
    for table in block.find_all('table'):
        rows = _table_rows(table)
        if not rows:
            continue
        head = rows[0]
        if len(head) == 3 and head[1:] and canonical_team(head[1]) in teams:
            for r in rows[1:]:
                if len(r) == 3 and r[0] in ('本塁打', '三塁打', '二塁打'):
                    for i, team in enumerate((canonical_team(head[1]), canonical_team(head[2]))):
                        for n in _names_in(r[i + 1]):
                            xbh.setdefault(team, Counter())[(n, r[0])] += 1
        elif head[:3] == ['打順', 'ポジション', '氏名']:
            bat_tables.append(rows[1:])
        elif head[:3] == ['氏名', '学年', '高校名']:
            pit_tables.append(rows[1:])

    for team, rows in zip(teams, bat_tables):
        for r in rows:
            if len(r) < 8 or not r[2]:
                continue
            name, grade, hs = r[2], to_int(r[3]), r[4]
            a = acc.setdefault((team, name), _Acc(team, name, grade, hs))
            line = a.bat = a.bat or BattingLine(doubles=0, triples=0, home_runs=0, rbis=0)
            line.games += 1
            line.at_bats += to_int(r[5]) or 0
            line.hits += to_int(r[6]) or 0
            line.rbis += to_int(r[7]) or 0
            line.doubles += xbh[team].pop((name, '二塁打'), 0)
            line.triples += xbh[team].pop((name, '三塁打'), 0)
            line.home_runs += xbh[team].pop((name, '本塁打'), 0)

    for team, rows in zip(teams, pit_tables):
        for r in rows:
            if len(r) < 7 or not r[0]:
                continue
            raw = r[0]
            decision = raw[0] if raw[0] in '〇○◯●' else ''
            name = raw.lstrip('〇○◯●△ ').strip()
            grade, hs = to_int(r[1]), r[2]
            a = acc.setdefault((team, name), _Acc(team, name, grade, hs))
            line = a.pit = a.pit or PitchingLine()
            outs = round((line.innings or 0) * 3) + round((parse_innings(r[3]) or 0) * 3)
            line.innings = round(outs // 3 + {0: 0, 1: 0.33, 2: 0.67}[outs % 3], 2)
            line.games += 1
            line.batters_faced = (line.batters_faced or 0) + (to_int(r[4]) or 0)
            line.hits_allowed = (line.hits_allowed or 0) + (to_int(r[5]) or 0)
            line.earned_runs = (line.earned_runs or 0) + (to_int(r[6]) or 0)
            if decision in '〇○◯' and decision:
                line.wins = (line.wins or 0) + 1
            elif decision == '●':
                line.losses = (line.losses or 0) + 1


def _score(block) -> Optional[Tuple[str, int, str, int]]:
    """スコア表から (先攻, 得点, 後攻, 得点)。"""
    table = block.select_one('table.match_score')
    if not table:
        return None
    rows = [r for r in _table_rows(table) if r and r[0]]
    if len(rows) < 2:
        return None
    try:
        return canonical_team(rows[0][0]), int(rows[0][-1]), canonical_team(rows[1][0]), int(rows[1][-1])
    except ValueError:
        return None


def league_blocks(blocks) -> List:
    """勝ち点制（先に2勝したほうが勝ち点）の対戦を超えた試合（優勝決定戦など）を除く。

    ページは日付順なので、同じ組み合わせで片方が2勝した後の対戦はリーグ戦の個人成績に数えない
    （連盟発表の個人成績と合わせるため）。1回総当たりの2部は2勝に届かないので影響しない。
    """
    wins: Dict[frozenset, Counter] = {}
    kept = []
    for b in blocks:
        s = _score(b)
        if not s:
            kept.append(b)
            continue
        a, ra, h, rh = s
        pair = frozenset((a, h))
        w = wins.setdefault(pair, Counter())
        if max(w.values(), default=0) >= 2:
            continue
        kept.append(b)
        if ra != rh:
            w[a if ra > rh else h] += 1
    return kept


def fetch_season(year: int, season: str, divisions=('1', '2'), supplement: bool = True) -> List[ExtPlayer]:
    out: List[ExtPlayer] = []
    for div in divisions:
        acc: Dict[Tuple[str, str], _Acc] = {}
        url = division_url(year, season, div)
        for block in league_blocks(soup_of(fetch_html(url)).select('div.match_data')):
            _parse_block(block, div, acc)
        for (team, name), a in acc.items():
            hs = a.high_school
            out.append(ExtPlayer(
                source=SOURCE, ext_key=f'{team}|{name}|{hs}', display_name=name, team=team,
                high_school=hs, batting=a.bat, pitching=a.pit, profile_url=url,
                extra={'tournament': DIVISIONS[div], 'grade': str(a.grade or '')},
            ))
    _apply_ranking(year, season, out)
    if supplement:
        from stats_sync import kyureki
        _verify_messages.extend(kyureki.supplement_shuto(year, season, out, canonical_team))
    return out


_verify_messages: List[str] = []


def _apply_ranking(year: int, season: str, players: List[ExtPlayer]) -> None:
    """上位ランキングに載っている選手は、連盟発表のシーズン成績で上書きする（奪三振・打席も埋まる）。

    試合記録の足し上げとの差は _verify_messages に残し、verify() で表示する。
    """
    _verify_messages.clear()
    url = f'{BASE}stats{year}{"haru" if season == "spring" else "aki"}.html'
    try:
        soup = soup_of(fetch_html(url))
    except Exception as e:
        _verify_messages.append(f'ランキングを読めません: {e}')
        return
    checked = diff = 0
    for table in soup.find_all('table'):
        rows = _table_rows(table)
        head = rows[0] if rows else []
        is_pitch = '投球回' in head
        for r in rows:
            if len(r) < 12 or not r[0].isdigit():
                continue
            team = canonical_team(r[2])
            full_key = name_key(r[1])  # 春は「髙橋 賢臣」のように空白入り
            cands = [e for e in players if e.team == team and full_key.startswith(name_key(e.display_name))
                     and (e.pitching if is_pitch else e.batting)]
            checked += 1
            if not cands:
                _verify_messages.append(f'足し上げに居ない: {r[1]}（{team}）')
                continue
            e = max(cands, key=lambda x: len(x.display_name))
            e.full_name = e.full_name or None
            if is_pitch:
                p = e.pitching
                official = (to_int(r[4]), parse_innings(r[7]), to_int(r[10]))
                mine = (p.games, p.innings, p.earned_runs)
                p.games, p.innings, p.earned_runs = official[0] or p.games, official[1] or p.innings, official[2]
                p.wins, p.losses = to_int(r[5]), to_int(r[6])
                p.strikeouts, p.runs = to_int(r[8]), to_int(r[9])
            else:
                b = e.batting
                official = (to_int(r[4]), to_int(r[6]), to_int(r[7]), to_int(r[9]))
                mine = (b.games, b.at_bats, b.hits, b.rbis)
                b.games, b.at_bats, b.hits = official[0] or b.games, official[1] or 0, official[2] or 0
                b.plate_appearances, b.home_runs, b.rbis = to_int(r[5]), to_int(r[8]), official[3]
            if official != mine:
                diff += 1
                _verify_messages.append(f'連盟発表で上書き: {r[1]}（{team}） 発表={official} 足し上げ={mine}')
    _verify_messages.insert(0, f'ランキング {checked}人と突き合わせ: 足し上げと違ったのは {diff}人（連盟発表の数字を採用）')


def fill_profile(player: ExtPlayer) -> None:
    return None  # フルネームは載っていない（出身高校で照合する）


def source_url(ext: ExtPlayer, year: int, season: str) -> str:
    return ext.profile_url or BASE


def verify(year: int, season: str, ext_players: List[ExtPlayer]) -> List[str]:
    """fetch_season でランキングと突き合わせた結果を返す。"""
    return list(_verify_messages)
