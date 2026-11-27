"""東京六大学野球連盟（big6.gr.jp）。

- チーム別の全選手成績（打撃・投手）がある。表の名前は姓だけで、選手ID（p=AW25TK2 など）へのリンク付き。
- 選手ページにフルネーム・入学年・出身高校が載るので、照合はそちらで行う。
- 打撃は「四死球」「犠打」のみ（四球/死球・犠飛の内訳なし）。投手も「四死球」のみ。
"""

import re
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

from stats_sync.common import (
    BattingLine, ExtPlayer, PitchingLine, cell_text, fetch_html, parse_innings, soup_of, to_int,
)

SOURCE = 'big6'
TOURNAMENT = '東京六大学'
BASE = 'https://www.big6.gr.jp/system/prog/'

# 連盟サイトのチーム記号 → DB の大学名の表記
TEAMS: Dict[str, str] = {
    'W': '早稲田大', 'K': '慶應義塾大', 'M': '明治大', 'H': '法政大', 'R': '立教大', 'T': '東京大',
}


def season_code(year: int, season: str) -> str:
    return f"{year}{'s' if season == 'spring' else 'a'}"


def team_url(team: str, kind: str, year: int, season: str) -> str:
    return (f"{BASE}kojinseiseki_season.php?gs=season&t={team}&m=pc&k={kind}"
            f"&e=league&s={season_code(year, season)}")


def is_existing_tournament(name: Optional[str]) -> bool:
    """既存の stats.tournament が東京六大学のリーグ戦を指すか（表記ゆれ込み）。"""
    t = (name or '').replace(' ', '')
    return t.startswith('東京六大学') or t in ('六大学', '六大学リーグ')


def _read_table(html: str, header_word: str):
    """見出しに header_word を含む表から、(見出し, [(セル文字列, 選手ID)]) を返す。"""
    soup = soup_of(html)
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        header = None
        out = []
        for tr in rows:
            cells = tr.find_all(['td', 'th'])
            texts = [cell_text(c) for c in cells]
            if header is None:
                if '氏名' in texts and header_word in texts:
                    header = texts
                continue
            if len(texts) != len(header) or not texts[0] or texts[0] == '合計':
                continue
            link = tr.find('a', href=re.compile(r'[?&]p='))
            pid = None
            if link:
                pid = parse_qs(urlparse(link['href']).query).get('p', [None])[0]
            out.append((texts, pid, urljoin(BASE, link['href']) if link else None))
        if header:
            return header, out
    return None, []


def _col(header: List[str], texts: List[str], name: str) -> Optional[str]:
    return texts[header.index(name)] if name in header else None


def fetch_team_season(team: str, year: int, season: str) -> List[ExtPlayer]:
    """1チーム・1シーズンの全選手（打撃・投手をまとめた ExtPlayer の一覧）。"""
    players: Dict[str, ExtPlayer] = {}

    def get(pid: str, name: str, url: Optional[str]) -> ExtPlayer:
        if pid not in players:
            players[pid] = ExtPlayer(source=SOURCE, ext_key=pid, display_name=name,
                                     team=TEAMS[team], profile_url=url)
        return players[pid]

    header, rows = _read_table(fetch_html(team_url(team, 'batting', year, season)), '打数')
    for texts, pid, url in rows:
        if not pid:
            continue
        c = lambda n: _col(header, texts, n)  # noqa: E731
        get(pid, texts[0], url).batting = BattingLine(
            games=to_int(c('試合')) or 0, plate_appearances=to_int(c('打席')),
            at_bats=to_int(c('打数')) or 0, runs=to_int(c('得点')), hits=to_int(c('安打')) or 0,
            doubles=to_int(c('二塁打')), triples=to_int(c('三塁打')), home_runs=to_int(c('本塁打')),
            rbis=to_int(c('打点')), steals=to_int(c('盗塁')),
            walks=to_int(c('四死球')), hit_by_pitch=0, sacrifice_flies=None,
            strikeouts=to_int(c('三振')),
        )

    header, rows = _read_table(fetch_html(team_url(team, 'pitching', year, season)), '投球回')
    for texts, pid, url in rows:
        if not pid:
            continue
        c = lambda n: _col(header, texts, n)  # noqa: E731
        get(pid, texts[0], url).pitching = PitchingLine(
            games=to_int(c('試合')) or 0, wins=to_int(c('勝利')), losses=to_int(c('敗戦')),
            batters_faced=to_int(c('打者')), innings=parse_innings(c('投球回')),
            hits_allowed=to_int(c('安打')), home_runs_allowed=to_int(c('本塁打')),
            walks_plus_hbp=to_int(c('四死球')), strikeouts=to_int(c('三振')),
            runs=to_int(c('失点')), earned_runs=to_int(c('自責点')),
        )
    return list(players.values())


_PROFILE_RE = re.compile(r'([^\s（(]+)[\s　]+([^\s（(]+)\s*[（(](\d{4})年入学[・･]')


def _until_closing(text: str) -> str:
    """「高田（岩手））…」のように括弧が入れ子でも、外側の閉じ括弧の手前までを返す。"""
    depth = 0
    for i, ch in enumerate(text):
        if ch in '（(':
            depth += 1
        elif ch in '）)':
            if depth == 0:
                return text[:i]
            depth -= 1
    return text


def fill_profile(player: ExtPlayer) -> None:
    """選手ページからフルネーム・入学年・出身高校を読む（照合が必要な選手だけ呼ぶ）。"""
    if not player.profile_url or player.full_name:
        return
    text = soup_of(fetch_html(player.profile_url)).get_text(' ', strip=True)
    m = _PROFILE_RE.search(text)
    if m:
        player.full_name = f'{m.group(1)} {m.group(2)}'
        player.entry_year = int(m.group(3))
        player.high_school = _until_closing(text[m.end():]).strip()


def source_url(ext: ExtPlayer, year: int, season: str) -> str:
    team = next(k for k, v in TEAMS.items() if v == ext.team)
    return team_url(team, 'batting' if ext.batting else 'pitching', year, season)


def fetch_season(year: int, season: str) -> List[ExtPlayer]:
    out: List[ExtPlayer] = []
    for team in TEAMS:
        out.extend(fetch_team_season(team, year, season))
    return out
