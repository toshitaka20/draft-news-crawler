"""東都大学野球連盟（tohto-bbl.com）。

- シーズン成績表は規定到達者だけなので、試合ごとの公式記録を足し上げて全選手分を作る。
  - 打撃: gameinfo/detail.php（全選手の打席・打数・得点・安打・二塁・三塁・本塁・打点・盗塁・犠打飛・四死球・三振）
  - 投手: gameinfo/result.php（回数・打者・被安・四死・三振・自責・勝負）
- 試合の記録は「名字（同姓は（徹）などの添え字）＋出身高校」なので、選手名鑑
  （player/playerinfo.php?UNIVID=）の「氏名・出身高校」でフルネームに直す。
- ページは Shift_JIS。
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from database.player_matcher import name_key, school_key
from stats_sync.common import (
    BattingLine, ExtPlayer, PitchingLine, cell_text, fetch_html, parse_innings, soup_of, strip_paren,
    to_int,
)

SOURCE = 'tohto'
BASE = 'http://www.tohto-bbl.com/'
DIVISIONS = {'01': '東都1部', '02': '東都2部', '03': '東都3部', '04': '東都4部'}
DEFAULT_DIVISIONS = ('01', '02')
TOURNAMENT = '東都'  # 表示用（実際の行は 東都1部 / 東都2部 …）

# 選手名鑑の UNIVID → DB の大学名の表記
UNIVS: Dict[str, str] = {
    '01': '青山学院大', '02': '亜細亜大', '03': '学習院大', '04': '國學院大', '05': '国士舘大',
    '06': '駒澤大', '07': '芝浦工業大', '08': '順天堂大', '09': '上智大', '10': '成蹊大',
    '11': '専修大', '12': '大正大', '13': '拓殖大', '14': '中央大', '15': '東京科学大',
    '16': '東京農業大', '17': '東洋大', '18': '日本大', '19': '一橋大', '20': '東京都市大',
    '21': '立正大', '22': '帝京平成大',
}
# 試合記録での略称 → DB の大学名
ALIASES = {'青学大': '青山学院大', '帝平大': '帝京平成大', '東農大': '東京農業大', '国学院大': '國學院大'}


def season_id(season: str) -> str:
    return '01' if season == 'spring' else '02'


def is_existing_tournament(name: Optional[str]) -> bool:
    return (name or '').replace(' ', '').startswith('東都')


def canonical_team(abbr: str) -> str:
    abbr = abbr.strip()
    if abbr in ALIASES:
        return ALIASES[abbr]
    key = school_key(abbr)
    for full in UNIVS.values():
        if school_key(full) == key:
            return full
    return abbr


def _rows(html: str) -> List[List[str]]:
    soup = soup_of(html)
    return [[cell_text(c) for c in tr.find_all(['td', 'th'])] for tr in soup.find_all('tr')]


def game_ids(year: int, season: str, division: str) -> List[str]:
    html = fetch_html(f'{BASE}gameinfo/schedule.php?YEAR={year}&SEASONID={season_id(season)}&LEAGUEID={division}')
    ids = re.findall(r'result\.php\?YEAR=\d+&(?:amp;)?SEASONID=\d+&(?:amp;)?LEAGUEID=\d+&(?:amp;)?GAMEID=(\d+)', html)
    return sorted(set(ids), key=ids.index)


def _hs(text: str) -> str:
    return text.strip().strip('()（）').strip()


@dataclass
class _Acc:
    team: str
    name: str            # 試合記録の表記（添え字つき）
    high_school: str
    bat: Optional[BattingLine] = None
    pit: Optional[PitchingLine] = None


def _add_bat(line: BattingLine, cells: List[str]) -> None:
    pa, ab, r, h, d2, d3, hr, _tb, rbi, sb, sac, bb, so = (to_int(x) or 0 for x in cells[:13])
    line.games += 1
    line.plate_appearances = (line.plate_appearances or 0) + pa
    line.at_bats += ab
    line.runs = (line.runs or 0) + r
    line.hits += h
    line.doubles = (line.doubles or 0) + d2
    line.triples = (line.triples or 0) + d3
    line.home_runs = (line.home_runs or 0) + hr
    line.rbis = (line.rbis or 0) + rbi
    line.steals = (line.steals or 0) + sb
    line.walks = (line.walks or 0) + bb       # 四死球の合計（内訳なし）
    line.hit_by_pitch = 0
    line.strikeouts = (line.strikeouts or 0) + so
    # 犠打飛は犠打と犠飛が分けられないので、出塁率の分母には入れない（sacrifice_flies は空）


def _add_pit(line: PitchingLine, cells: List[str]) -> None:
    decision, ip, bf, _np, h, bb, so, er = cells[:8]
    outs_before = round((line.innings or 0) * 3)
    add = parse_innings(ip) or 0
    total_outs = outs_before + round(add * 3)
    line.innings = round(total_outs // 3 + {0: 0, 1: 0.33, 2: 0.67}[total_outs % 3], 2)
    line.games += 1
    line.batters_faced = (line.batters_faced or 0) + (to_int(bf) or 0)
    line.hits_allowed = (line.hits_allowed or 0) + (to_int(h) or 0)
    line.walks_plus_hbp = (line.walks_plus_hbp or 0) + (to_int(bb) or 0)
    line.strikeouts = (line.strikeouts or 0) + (to_int(so) or 0)
    line.earned_runs = (line.earned_runs or 0) + (to_int(er) or 0)
    if decision.startswith('勝'):
        line.wins = (line.wins or 0) + 1
    elif decision.startswith('負'):
        line.losses = (line.losses or 0) + 1


def _game(year: int, season: str, division: str, gid: str, acc: Dict[Tuple[str, str, str], _Acc]) -> None:
    q = f'YEAR={year}&SEASONID={season_id(season)}&LEAGUEID={division}&GAMEID={gid}'
    # 打撃（詳細）: チーム名の見出し行 → 選手行（打順, 守備, 名前, (高校), 打席…）
    team = None
    for cells in _rows(fetch_html(f'{BASE}gameinfo/detail.php?{q}')):
        if len(cells) >= 10 and cells[1] == '打席':
            team = canonical_team(cells[0])
            continue
        if team and len(cells) >= 17 and cells[3].startswith('('):
            key = (team, strip_paren(cells[2]), _hs(cells[3]))
            a = acc.setdefault(key, _Acc(team, cells[2], _hs(cells[3])))
            a.bat = a.bat or BattingLine()
            _add_bat(a.bat, cells[4:])
    # 投手（結果）: スコア表の1行目=先攻、2行目=後攻。投手表はその順に並ぶ
    rows = _rows(fetch_html(f'{BASE}gameinfo/result.php?{q}'))
    teams = [canonical_team(r[0]) for r in rows if len(r) >= 11 and r[0] and all(re.fullmatch(r'[0-9xX×]*', c) for c in r[1:-3])]
    t_idx = -1
    for cells in rows:
        if cells and cells[0].replace(' ', '') == '名前出身校':
            t_idx += 1
            continue
        if t_idx >= 0 and len(cells) >= 9 and re.search(r'[(（]', cells[0]) and t_idx < len(teams):
            # 「石野（蓮）(報徳学園)」のように添え字があるので、最後の括弧を出身高校とみなす
            m = re.match(r'^(.*)[(（]([^()（）]*)[)）]\s*$', cells[0])
            if not m:
                continue
            name, hs = m.group(1).strip(), m.group(2).strip()
            key = (teams[t_idx], strip_paren(name), hs)
            a = acc.setdefault(key, _Acc(teams[t_idx], name, hs))
            a.pit = a.pit or PitchingLine()
            _add_pit(a.pit, cells[1:])


def roster(univ_id: str) -> Dict[str, List[Tuple[str, str]]]:
    """選手名鑑：名字キー → [(フルネーム, 高校キー)]。"""
    out: Dict[str, List[Tuple[str, str]]] = {}
    for cells in _rows(fetch_html(f'{BASE}player/playerinfo.php?UNIVID={univ_id}')):
        if len(cells) < 5 or cells[0] in ('位 置', '部長', '監督', 'コーチ') or not cells[2]:
            continue
        full = re.sub(r'\s+', ' ', cells[2]).strip()
        parts = full.split(' ')
        if len(parts) < 2:
            continue
        out.setdefault(name_key(parts[0]), []).append((full, _hs_key(cells[4])))
    return out


def resolve_full_name(members: Dict[str, List[Tuple[str, str]]], display: str, hs: str) -> Optional[str]:
    """試合記録の「石野（蓮）」＋出身高校から、名鑑のフルネームを1人に決める。決まらなければ None。"""
    surname = strip_paren(display)
    m = re.search(r'[（(]([^）)]+)[）)]', display)
    suffix = m.group(1) if m else ''
    cands = members.get(name_key(surname), [])
    hk = _hs_key(hs)
    by_hs = [c for c in cands if c[1] and hk and (c[1] == hk or c[1] in hk or hk in c[1])]
    pool = by_hs or (cands if len(cands) == 1 else [])
    if suffix:
        pool = [c for c in (by_hs or cands) if c[0].split(' ', 1)[1].startswith(suffix)]
    names = sorted({c[0] for c in pool})
    return names[0] if len(names) == 1 else None


def _hs_key(text: str) -> str:
    t = re.sub(r'[（(][^）)]*[）)]', '', text or '').replace('辯', '弁').replace('第一', '一')
    t = t.replace('舍', '舎').replace('學園', '').replace('学園', '')
    t = re.sub(r'(高等学校|高校|高)$', '', t.strip())
    return school_key(t) or ''


def fetch_season(year: int, season: str, divisions=DEFAULT_DIVISIONS) -> List[ExtPlayer]:
    acc: Dict[Tuple[str, str, str], _Acc] = {}
    division_of: Dict[str, str] = {}
    for div in divisions:
        for gid in game_ids(year, season, div):
            before = set(acc)
            _game(year, season, div, gid, acc)
            for key in set(acc) - before:
                division_of[key[0]] = div
    for key in acc:
        division_of.setdefault(key[0], divisions[0])

    rosters: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}
    out: List[ExtPlayer] = []
    for (team, surname, hs), a in acc.items():
        univ_id = next((k for k, v in UNIVS.items() if v == team), None)
        if univ_id and univ_id not in rosters:
            rosters[univ_id] = roster(univ_id)
        full = resolve_full_name(rosters.get(univ_id, {}), a.name, hs)
        div = division_of[team]
        ext = ExtPlayer(
            source=SOURCE, ext_key=f'{team}|{full or a.name}|{hs}', display_name=a.name, team=team,
            full_name=full, high_school=hs, batting=a.bat, pitching=a.pit,
            profile_url=f'{BASE}gameinfo/schedule.php?YEAR={year}&SEASONID={season_id(season)}&LEAGUEID={div}',
            extra={'tournament': DIVISIONS[div]},
        )
        out.append(ext)
    return out


def fill_profile(player: ExtPlayer) -> None:
    """フルネームは fetch_season で名鑑から入れているので、ここでは何もしない。"""
    return None


def source_url(ext: ExtPlayer, year: int, season: str) -> str:
    return ext.profile_url or BASE


def verify(year: int, season: str, ext_players: List[ExtPlayer], divisions=DEFAULT_DIVISIONS) -> List[str]:
    """足し上げた打撃成績を、連盟発表の規定到達者のシーズン成績（打数・安打・打点）と突き合わせる。"""
    by_key = {(e.team, e.display_name): e for e in ext_players if e.batting}
    messages, checked = [], 0
    for div in divisions:
        url = f'{BASE}gameinfo/{year}/{int(div)}battrer_{"s" if season == "spring" else "a"}.html'
        try:
            rows = _rows(fetch_html(url))
        except Exception as e:  # 過去年度でページが無いなど
            messages.append(f'{DIVISIONS[div]} の規定到達者表を読めません: {e}')
            continue
        for cells in rows:
            if len(cells) < 21 or not cells[0].isdigit():
                continue
            team, name = canonical_team(cells[2]), cells[1]
            official = (to_int(cells[5]), to_int(cells[7]), to_int(cells[12]))
            ext = by_key.get((team, name))
            checked += 1
            if not ext:
                messages.append(f'足し上げに居ない: {name}（{team}）')
                continue
            mine = (ext.batting.at_bats, ext.batting.hits, ext.batting.rbis)
            if mine != official:
                messages.append(f'食い違い: {name}（{team}） 公式(打数,安打,打点)={official} 足し上げ={mine}')
        # 投手（規定投球回到達者）: 回数・奪三振・自責点
        p_by_key = {(e.team, e.display_name): e for e in ext_players if e.pitching}
        try:
            prow = _rows(fetch_html(f'{BASE}gameinfo/{year}/{int(div)}pitcher_{"s" if season == "spring" else "a"}.html'))
        except Exception:
            prow = []
        for cells in prow:
            if len(cells) < 20 or not cells[0].isdigit():
                continue
            team, name = canonical_team(cells[2]), cells[1]
            official = (parse_innings(cells[10]), to_int(cells[14]), to_int(cells[18]))
            ext = p_by_key.get((team, name))
            checked += 1
            if not ext:
                messages.append(f'足し上げに居ない（投手）: {name}（{team}）')
                continue
            mine = (ext.pitching.innings, ext.pitching.strikeouts, ext.pitching.earned_runs)
            if mine != official:
                messages.append(f'食い違い（投手）: {name}（{team}） 公式(回,奪三振,自責)={official} 足し上げ={mine}')
    messages.insert(0, f'規定到達者 {checked}人と突き合わせ: 食い違い {sum(1 for m in messages if m.startswith(("食い違い", "足し上げ")))}人')
    return messages
