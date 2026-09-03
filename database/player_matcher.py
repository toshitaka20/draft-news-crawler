"""
志望届名簿の氏名と players テーブルの名寄せ。

名簿サイト（高野連・大学野球連盟）とDraft-WatchのDBでは、同じ選手でも
  - 旧字体・異体字（岡﨑/岡崎、牟禮/牟礼、髙田/高田）
  - 姓名の区切り（全角スペース/半角スペース/区切りなし）
  - 学校名の表記（金沢学院大附/金沢学院大付、千葉商科大学/千葉商科大）
がずれる。ここでは「氏名キー」「かなキー」「学校キー」の3系統で照合し、
一意に決まらない場合は自動更新せず ambiguous として人手に回す。
"""

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from utils import normalize_player_key, normalize_school_key

# utils.KYUJITAI_MAP でカバーしていない異体字。氏名の名寄せ用に追加で寄せる。
# （KYUJITAI_MAP 自体は topic_key 生成に使われており、変更すると既存キーが動くのでここで上乗せする）
EXTRA_VARIANT_MAP = str.maketrans({
    '濵': '浜', '嵜': '崎', '冨': '富', '桒': '桑', '栁': '柳', '檜': '桧',
    '禮': '礼', '來': '来', '曾': '曽', '藝': '芸', '亞': '亜', '應': '応',
    '榮': '栄', '壽': '寿', '兒': '児', '內': '内', '步': '歩', '每': '毎',
    '瀧': '滝', '龍': '竜', '嶌': '島', '峯': '峰', '祿': '禄',
    '當': '当', '寬': '寛', '樂': '楽', '淸': '清', '靑': '青', '鄕': '郷',
    '曻': '昇', '禎': '禎', '賴': '頼', '莊': '荘', '將': '将', '獻': '献',
})

_KATAKANA_START, _KATAKANA_END = 0x30A1, 0x30F6
_HIRAGANA_OFFSET = 0x60


def name_key(name: Optional[str]) -> str:
    """氏名の照合キー（旧字体・異体字・空白・大小文字を吸収）。"""
    key = normalize_player_key(name) or ''
    return key.translate(EXTRA_VARIANT_MAP)


def kana_key(kana: Optional[str]) -> str:
    """ふりがなの照合キー（カタカナ→ひらがな、空白・記号除去）。"""
    if not kana:
        return ''
    text = unicodedata.normalize('NFKC', kana)
    text = ''.join(
        chr(ord(ch) - _HIRAGANA_OFFSET) if _KATAKANA_START <= ord(ch) <= _KATAKANA_END else ch
        for ch in text
    )
    return re.sub(r'[^ぁ-んー]', '', text)


def school_key(school: Optional[str]) -> str:
    """学校名の照合キー。utils の正規化に加えて「附/付」などの揺れを寄せる。"""
    key = normalize_school_key(school) or ''
    return key.replace('附', '付').replace('ヶ', 'ケ').replace('ヵ', 'ケ')


def _school_compatible(left: str, right: str) -> bool:
    """学校キーが一致、または片方がもう片方を含む（略称関係）ならTrue。"""
    if not left or not right:
        return False
    if left == right:
        return True
    return left in right or right in left


@dataclass
class MatchResult:
    entry: Dict[str, Any]
    status: str  # 'matched' | 'ambiguous' | 'unmatched'
    player: Optional[Dict[str, Any]] = None
    matched_by: Optional[str] = None  # 'name' | 'name+school' | 'kana'
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)


class PlayerMatcher:
    """players 全件をメモリに載せて、志望届エントリと名寄せする。"""

    def __init__(self, players: List[Dict[str, Any]]):
        self.players = players
        self._by_name: Dict[str, List[Dict[str, Any]]] = {}
        self._by_kana: Dict[str, List[Dict[str, Any]]] = {}
        for player in players:
            player['_name_key'] = name_key(player.get('name'))
            player['_kana_key'] = kana_key(player.get('name_kana'))
            player['_school_key'] = school_key(player.get('team'))
            if player['_name_key']:
                self._by_name.setdefault(player['_name_key'], []).append(player)
            if player['_kana_key']:
                self._by_kana.setdefault(player['_kana_key'], []).append(player)

    def match(self, entry: Dict[str, Any], draft_year: Optional[int] = None) -> MatchResult:
        entry_name_key = name_key(entry.get('name'))
        entry_kana_key = kana_key(entry.get('name_kana'))
        entry_school_key = school_key(entry.get('school'))
        entry_category = entry.get('category')

        matched_by = 'name'
        candidates = list(self._by_name.get(entry_name_key, []))
        if not candidates and entry_kana_key:
            candidates = list(self._by_kana.get(entry_kana_key, []))
            matched_by = 'kana'

        if not candidates:
            return MatchResult(
                entry=entry,
                status='unmatched',
                suggestions=self._suggest(entry_name_key, entry_school_key, entry_category),
            )

        # 複数ヒットは学校 → カテゴリ → ドラフト年 の順で絞る。
        if len(candidates) > 1:
            narrowed = [p for p in candidates if _school_compatible(entry_school_key, p['_school_key'])]
            if narrowed:
                candidates, matched_by = narrowed, f'{matched_by}+school'
        if len(candidates) > 1 and entry_category:
            narrowed = [p for p in candidates if p.get('category') == entry_category]
            if narrowed:
                candidates = narrowed
        if len(candidates) > 1 and draft_year:
            narrowed = [p for p in candidates if p.get('draft_year') == draft_year]
            if narrowed:
                candidates = narrowed

        if len(candidates) > 1:
            return MatchResult(entry=entry, status='ambiguous', candidates=candidates)

        player = candidates[0]
        warnings: List[str] = []
        if entry_school_key and player['_school_key'] and not _school_compatible(entry_school_key, player['_school_key']):
            warnings.append(f"所属が不一致（名簿: {entry.get('school')} / DB: {player.get('team')}）")
        if entry_category and player.get('category') and player['category'] != entry_category:
            warnings.append(f"カテゴリが不一致（名簿: {entry_category} / DB: {player['category']}）")
        if draft_year and player.get('draft_year') and player['draft_year'] != draft_year:
            warnings.append(f"ドラフト年が不一致（名簿: {draft_year} / DB: {player['draft_year']}）")

        return MatchResult(
            entry=entry,
            status='matched',
            player=player,
            matched_by=matched_by,
            candidates=candidates,
            warnings=warnings,
        )

    def _suggest(self, entry_name_key: str, entry_school_key: str, entry_category: Optional[str],
                 limit: int = 3) -> List[Dict[str, Any]]:
        """
        未ヒット時に「表記ゆれで取りこぼしている可能性がある登録選手」を挙げる。
        自動リンクはせず、GitHub issue に載せて人手確認に回すための材料。
        """
        if not entry_name_key:
            return []

        scored: List[Dict[str, Any]] = []
        for player in self.players:
            player_name_key = player.get('_name_key') or ''
            if not player_name_key:
                continue
            same_school = _school_compatible(entry_school_key, player['_school_key'])
            if not same_school and player.get('category') != entry_category:
                continue
            ratio = SequenceMatcher(None, entry_name_key, player_name_key).ratio()
            threshold = 0.6 if same_school else 0.85
            if ratio < threshold:
                continue
            scored.append({
                'id': player.get('id'),
                'name': player.get('name'),
                'team': player.get('team'),
                'draft_year': player.get('draft_year'),
                'declared': player.get('declared'),
                'similarity': round(ratio, 2),
                'same_school': same_school,
            })

        scored.sort(key=lambda s: (s['same_school'], s['similarity']), reverse=True)
        return scored[:limit]
