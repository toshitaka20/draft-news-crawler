"""連盟サイトの取得・表の読み取り・成績行の組み立てで共通に使う部品。"""

import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

USER_AGENT = 'Mozilla/5.0 (compatible; DraftWatchStatsBot/1.0)'
REQUEST_INTERVAL_SEC = 1.5  # 連盟サイトに負担をかけないよう、1件ずつ間をあける

_last_request_at = 0.0


def fetch_html(url: str, timeout: int = 30) -> str:
    """URL を取得して文字列で返す（文字コードはページの宣言→推定の順で決める）。"""
    global _last_request_at
    wait = REQUEST_INTERVAL_SEC - (time.time() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=timeout)
    _last_request_at = time.time()
    resp.raise_for_status()
    head = resp.content[:4096].decode('ascii', errors='ignore')
    m = re.search(r'charset=["\']?([\w-]+)', head, re.I)
    if m:
        enc = m.group(1).lower()
        resp.encoding = 'cp932' if enc in ('shift_jis', 'shift-jis', 'sjis', 'x-sjis') else enc
    elif not resp.encoding or resp.encoding.lower() in ('iso-8859-1', 'ascii'):
        resp.encoding = resp.apparent_encoding
    return resp.text


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, 'html.parser')


def cell_text(el) -> str:
    return re.sub(r'\s+', ' ', el.get_text(' ', strip=True)).strip()


def to_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = unicodedata.normalize('NFKC', str(value)).strip()
    if text in ('', '-', '－', '—'):
        return None
    m = re.match(r'^-?\d+', text)
    return int(m.group()) if m else None


def parse_innings(value: Optional[str]) -> Optional[float]:
    """「37 1/3」「0 2/3」「24」を 37.33 / 0.67 / 24.0 にする（DB の投球回の書き方）。"""
    if value is None:
        return None
    text = unicodedata.normalize('NFKC', str(value)).strip()
    if not text or text in ('-',):
        return None
    m = re.match(r'^(\d+)?\s*(?:(\d)\s*/\s*3)?$', text)
    if not m or (m.group(1) is None and m.group(2) is None):
        return None
    whole = int(m.group(1) or 0)
    thirds = int(m.group(2) or 0)
    return round(whole + {0: 0.0, 1: 0.33, 2: 0.67}[thirds], 2)


def innings_outs(innings: Optional[float]) -> int:
    """37.33 → 112 アウト（割り算の誤差を避けるため、計算はアウト数で行う）。"""
    if not innings:
        return 0
    whole = int(innings)
    frac = round(innings - whole, 2)
    return whole * 3 + (1 if abs(frac - 0.33) < 0.02 else 2 if abs(frac - 0.67) < 0.02 else 0)


def safe_ratio(num: float, den: float, digits: int) -> Optional[float]:
    if not den:
        return None
    value = round(num / den, digits)
    return value if abs(value) < 100 else None  # numeric 桁あふれ（100以上）は null


@dataclass
class BattingLine:
    games: int = 0
    plate_appearances: Optional[int] = None
    at_bats: int = 0
    runs: Optional[int] = None
    hits: int = 0
    doubles: Optional[int] = None
    triples: Optional[int] = None
    home_runs: Optional[int] = None
    rbis: Optional[int] = None
    steals: Optional[int] = None
    walks: Optional[int] = None          # 四死球しか出ない連盟は合計をここに入れ、hit_by_pitch=0 にする
    hit_by_pitch: Optional[int] = None
    sacrifice_flies: Optional[int] = None
    strikeouts: Optional[int] = None


@dataclass
class PitchingLine:
    games: int = 0
    wins: Optional[int] = None
    losses: Optional[int] = None
    batters_faced: Optional[int] = None
    innings: Optional[float] = None
    hits_allowed: Optional[int] = None
    home_runs_allowed: Optional[int] = None
    walks_plus_hbp: Optional[int] = None
    walks: Optional[int] = None
    hit_by_pitch: Optional[int] = None
    strikeouts: Optional[int] = None
    runs: Optional[int] = None
    earned_runs: Optional[int] = None


@dataclass
class ExtPlayer:
    """連盟サイト上の選手1人分（1シーズン）。"""
    source: str
    ext_key: str
    display_name: str              # 表に出ている表記（姓だけのことが多い）
    team: str                      # DB の大学名の表記に寄せたもの
    full_name: Optional[str] = None
    high_school: Optional[str] = None
    entry_year: Optional[int] = None
    batting: Optional[BattingLine] = None
    pitching: Optional[PitchingLine] = None
    profile_url: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)


def batting_row(line: BattingLine) -> Dict:
    """stats の打者行（投球列は0）。指標は内訳から計算して入れる（画面側でも再計算される）。"""
    walks = line.walks or 0
    hbp = line.hit_by_pitch or 0
    sf = line.sacrifice_flies or 0
    ab = line.at_bats or 0
    hits = line.hits or 0
    singles = hits - (line.doubles or 0) - (line.triples or 0) - (line.home_runs or 0)
    tb = singles + 2 * (line.doubles or 0) + 3 * (line.triples or 0) + 4 * (line.home_runs or 0)
    avg = safe_ratio(hits, ab, 3)
    obp = safe_ratio(hits + walks + hbp, ab + walks + hbp + sf, 3)
    slg = safe_ratio(tb, ab, 3)
    return {
        'games': line.games, 'at_bats': ab, 'hits': hits,
        'home_runs': line.home_runs or 0, 'rbis': line.rbis or 0, 'steals': line.steals or 0,
        'doubles': line.doubles or 0, 'triples': line.triples or 0,
        'walks': walks, 'hit_by_pitch': hbp, 'sacrifice_flies': sf,
        'batter_strikeouts': line.strikeouts or 0,
        'avg': avg, 'obp': obp, 'slg': slg,
        'ops': round(obp + slg, 3) if obp is not None and slg is not None else None,
        'innings': 0, 'era': None, 'strikeouts': 0, 'strikeouts_per_9': None, 'hits_allowed': 0,
        'batting_avg_against': None, 'walks_plus_hit_by_pitch': 0, 'bbh_per_9': None, 'whip': None,
        'earned_runs': 0,
    }


def pitching_row(line: PitchingLine) -> Dict:
    """stats の投手行（打撃列は0）。"""
    outs = innings_outs(line.innings)
    ip = outs / 3 if outs else 0
    wph = line.walks_plus_hbp
    if wph is None and (line.walks is not None or line.hit_by_pitch is not None):
        wph = (line.walks or 0) + (line.hit_by_pitch or 0)
    er = line.earned_runs or 0
    return {
        'games': line.games, 'at_bats': 0, 'hits': 0, 'home_runs': 0, 'rbis': 0, 'steals': 0,
        'doubles': 0, 'triples': 0, 'walks': line.walks or 0, 'hit_by_pitch': line.hit_by_pitch or 0,
        'sacrifice_flies': 0, 'batter_strikeouts': 0,
        'avg': None, 'obp': None, 'slg': None, 'ops': None,
        'innings': line.innings or 0,
        'era': safe_ratio(er * 9, ip, 2),
        'strikeouts': line.strikeouts or 0,
        'strikeouts_per_9': safe_ratio((line.strikeouts or 0) * 9, ip, 2),
        'hits_allowed': line.hits_allowed or 0,
        'batting_avg_against': None,
        'walks_plus_hit_by_pitch': wph or 0,
        'bbh_per_9': safe_ratio((wph or 0) * 9, ip, 2),
        'whip': safe_ratio((line.hits_allowed or 0) + (wph or 0), ip, 2),
        'earned_runs': er,
    }


def strip_paren(text: str) -> str:
    """「高橋（徹）」「高橋(佑)」→「高橋」。"""
    return re.sub(r'[（(][^）)]*[）)]', '', text or '').strip()


def split_list(values: List[str]) -> List[str]:
    return [v for v in (s.strip() for s in values) if v]
