"""
プロ志望届（プロ野球志望届）提出者名簿スクレイパー

- 高校: 日本高等学校野球連盟 https://www.jhbf.or.jp/pro-aspiring/{year}.html
  表: 都道府県 / 学校名 / 氏名 / 所属連盟受付日
- 大学: 全日本大学野球連盟 https://www.jubf.net/system/prog/procandidate.php?kind=all&year={year}
  「NPBドラフト対象者」「NPBドラフト対象外者」の2セクション。
  表: 連盟 / 学校名 / 氏名 / ふりがな / 所属連盟受付日

どちらのサイトも提出があるたびに追記されていく名簿ページなので、
毎回の全件取得＋差分判定（呼び出し側）を前提に1行1選手のdictで返す。
"""

import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from config import REQUEST_TIMEOUT

JHBF_URL_TEMPLATE = "https://www.jhbf.or.jp/pro-aspiring/{year}.html"
JUBF_URL_TEMPLATE = "https://www.jubf.net/system/prog/procandidate.php?kind=all&year={year}"

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)

# 名簿表で「氏名が空のプレースホルダ行」「見出し行」「集計行」を除くための語（空白除去後で判定）。
_NON_PLAYER_CELLS = {'合計', '氏名', '計'}


def _fetch_html(url: str) -> str:
    response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    # 高野連はレスポンスヘッダにcharsetが無く、requestsがISO-8859-1と誤判定して文字化けする。
    # ヘッダにcharsetが無ければ meta charset を見て、それも無ければUTF-8とみなす。
    content_type = (response.headers.get('Content-Type') or '').lower()
    if 'charset=' not in content_type:
        meta = re.search(rb'<meta[^>]+charset=["\']?\s*([\w-]+)', response.content[:4096], re.I)
        response.encoding = meta.group(1).decode('ascii', 'ignore') if meta else 'utf-8'
    return response.text


def _cell_text(cell) -> str:
    """セルのテキストを取り出す（全角スペースは半角へ寄せ、前後空白は落とす）。"""
    text = cell.get_text(' ', strip=True)
    return re.sub(r'\s+', ' ', text.replace('　', ' ')).strip()


def _normalize_person_name(name: str) -> str:
    """氏名セルの表記を「姓 名」（半角スペース区切り）に揃える。"""
    return re.sub(r'\s+', ' ', (name or '').replace('　', ' ')).strip()


def _clean_affiliation(value: str) -> str:
    """「石 川」のようにセル内で分かち書きされた都道府県名から空白を落とす。"""
    return re.sub(r'\s+', '', value or '')


def _is_player_row(cells: List[str], name_index: int) -> bool:
    if len(cells) <= name_index:
        return False
    name = re.sub(r'\s+', '', cells[name_index])
    if not name or name in _NON_PLAYER_CELLS:
        return False
    # 「合計 / 7名」のような集計行を除く。
    if re.fullmatch(r'\d+名', name):
        return False
    return True


def _header_cells(table) -> List[str]:
    first_row = table.find('tr')
    if not first_row:
        return []
    return [re.sub(r'\s+', '', _cell_text(c)) for c in first_row.find_all(['th', 'td'])]


def _is_roster_table(table) -> bool:
    header = _header_cells(table)
    return '氏名' in header and '学校名' in header


def fetch_jhbf_pro_aspiring(year: int = 2026, url: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    高野連のプロ志望届提出者一覧を取得する。
    """
    source_url = url or JHBF_URL_TEMPLATE.format(year=year)
    print(f"[志望届] 高野連ページ取得: {source_url}")
    soup = BeautifulSoup(_fetch_html(source_url), 'html.parser')

    entries: List[Dict[str, Any]] = []
    for table in soup.find_all('table'):
        if not _is_roster_table(table):
            continue
        for row in table.find_all('tr'):
            if row.find('th') and not row.find('td'):
                continue  # 見出し行
            cells = [_cell_text(c) for c in row.find_all(['th', 'td'])]
            if not _is_player_row(cells, name_index=2):
                continue
            entries.append({
                'category': 'high_school',
                'affiliation': _clean_affiliation(cells[0]),
                'school': _clean_affiliation(cells[1]),
                'name': _normalize_person_name(cells[2]),
                'name_kana': None,
                'received_date': cells[3] if len(cells) > 3 else '',
                'draft_eligible': True,  # 高野連ページは「NPBドラフト対象者」のみ掲載
                'source_url': source_url,
                'source_name': '日本高等学校野球連盟',
            })

    print(f"[志望届] 高校: {len(entries)}名")
    return entries


def fetch_jubf_pro_aspiring(year: int = 2026, url: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    全日本大学野球連盟のプロ志望届提出者一覧を取得する。
    「NPBドラフト対象外者」セクションの選手は draft_eligible=False で返す。
    """
    source_url = url or JUBF_URL_TEMPLATE.format(year=year)
    print(f"[志望届] 大学野球連盟ページ取得: {source_url}")
    html = _fetch_html(source_url)

    # セクション見出し（■NPBドラフト対象者 / ■NPBドラフト対象外者）でHTMLを分割し、
    # どちらのセクションの表かを判定できるようにする。
    section_marks = [
        (m.start(), re.sub(r'<[^>]+>', '', m.group(1)).strip())
        for m in re.finditer(r'<span class="section">(.*?)</span>', html, re.S)
    ]
    if not section_marks:
        section_marks = [(0, 'NPBドラフト対象者')]

    entries: List[Dict[str, Any]] = []
    for index, (start, heading) in enumerate(section_marks):
        end = section_marks[index + 1][0] if index + 1 < len(section_marks) else len(html)
        eligible = '対象外' not in heading
        soup = BeautifulSoup(html[start:end], 'html.parser')

        for table in soup.find_all('table'):
            if not _is_roster_table(table):
                continue
            last_federation = ''
            for row in table.find_all('tr'):
                if row.find('th') and not row.find('td'):
                    continue  # 見出し行
                cells = [_cell_text(c) for c in row.find_all(['th', 'td'])]
                if not _is_player_row(cells, name_index=2):
                    continue
                federation = _clean_affiliation(cells[0])
                # 同一連盟の2人目以降は「〃」で省略される。
                if federation in ('', '〃', '同'):
                    federation = last_federation
                else:
                    last_federation = federation
                entries.append({
                    'category': 'university',
                    'affiliation': federation,
                    'school': _clean_affiliation(cells[1]),
                    'name': _normalize_person_name(cells[2]),
                    'name_kana': _normalize_person_name(cells[3]) if len(cells) > 3 else None,
                    'received_date': cells[4] if len(cells) > 4 else '',
                    'draft_eligible': eligible,
                    'source_url': source_url,
                    'source_name': '全日本大学野球連盟',
                })

    eligible_count = sum(1 for e in entries if e['draft_eligible'])
    print(f"[志望届] 大学: {len(entries)}名（うちドラフト対象 {eligible_count}名）")
    return entries


def fetch_all_pro_aspiring(year: int = 2026, sleep_sec: float = 1.0) -> List[Dict[str, Any]]:
    """
    高校・大学の名簿をまとめて取得する。片方が落ちても取れた側は返す。
    """
    entries: List[Dict[str, Any]] = []

    try:
        entries.extend(fetch_jhbf_pro_aspiring(year))
    except Exception as e:
        print(f"[エラー] 高野連の志望届ページ取得失敗: {e}")

    time.sleep(sleep_sec)

    try:
        entries.extend(fetch_jubf_pro_aspiring(year))
    except Exception as e:
        print(f"[エラー] 大学野球連盟の志望届ページ取得失敗: {e}")

    return entries
