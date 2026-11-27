"""DB とのやり取り：選手の照合（player_stat_links）と stats の置き換え。"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from database.player_matcher import name_key, school_key
from stats_sync.common import ExtPlayer, batting_row, pitching_row, strip_paren

PAGE = 1000


def _all_rows(query_fn) -> List[Dict]:
    rows: List[Dict] = []
    start = 0
    while True:
        batch = query_fn().range(start, start + PAGE - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < PAGE:
            return rows
        start += PAGE


def _teams_match(a: Optional[str], b: Optional[str]) -> bool:
    """大学名の一致（「明治大学」「明治大」は同じ。「東京農業大北海道オホーツク」は東京農業大と別）。"""
    ka, kb = school_key(a), school_key(b)
    return bool(ka and kb and ka == kb)


def _hs_key(name: Optional[str]) -> str:
    """出身高校の照合キー（「高田（岩手）」の県名、「第一」「辯」の表記ゆれ、「高」の有無を寄せる）。"""
    text = re.sub(r'[（(][^）)]*[）)]?', '', name or '')
    text = text.replace('辯', '弁').replace('第一', '一').replace('第二', '二')
    text = text.replace('舍', '舎').replace('學園', '').replace('学園', '')
    text = re.sub(r'(高等学校|高校|高)$', '', text.strip())
    return school_key(text) or ''


def _hs_match(a: Optional[str], b: Optional[str]) -> bool:
    ka, kb = _hs_key(a), _hs_key(b)
    return bool(ka and kb and (ka == kb or ka in kb or kb in ka))


@dataclass
class Match:
    ext: ExtPlayer
    player: Dict
    how: str                    # 'link' | 'name'
    warnings: List[str] = field(default_factory=list)


@dataclass
class MatchReport:
    matches: List[Match] = field(default_factory=list)
    ambiguous: List[Tuple[ExtPlayer, List[Dict]]] = field(default_factory=list)
    unmatched_profiles: List[Tuple[ExtPlayer, List[Dict]]] = field(default_factory=list)


class StatsStore:
    def __init__(self, client):
        self.sb = client
        self.links_available = self._probe('player_stat_links', 'id')
        self.source_column_available = self._probe('stats', 'source')

    def _probe(self, table: str, column: str) -> bool:
        try:
            self.sb.table(table).select(column).limit(1).execute()
            return True
        except Exception:
            return False

    # ---- 照合 ---------------------------------------------------------------
    def load_university_players(self) -> List[Dict]:
        return _all_rows(lambda: self.sb.table('players')
                         .select('id,name,team,category,position,career,draft_year')
                         .eq('category', 'university'))

    def load_links(self, source: str) -> Dict[str, Dict]:
        if not self.links_available:
            return {}
        rows = _all_rows(lambda: self.sb.table('player_stat_links').select('*').eq('source', source))
        return {r['ext_key']: r for r in rows}

    def match(self, ext_players: List[ExtPlayer], players: List[Dict], links: Dict[str, Dict],
              fill_profile: Callable[[ExtPlayer], None]) -> MatchReport:
        """連盟サイトの選手を DB の選手に結びつける。

        1. player_stat_links に confirmed があればそれを使う（rejected は無視）。
        2. 無ければ、同じ大学で姓が前方一致する DB 選手を探し、居たときだけ選手ページを読んで
           フルネームの完全一致（異体字は寄せる）で決める。1人に決まらなければ人の確認に回す。
        """
        by_id = {p['id']: p for p in players}
        report = MatchReport()
        for ext in ext_players:
            link = links.get(ext.ext_key)
            if link and link['status'] == 'rejected':
                continue
            if link and link['status'] == 'confirmed' and link['player_id'] in by_id:
                report.matches.append(Match(ext, by_id[link['player_id']], 'link'))
                continue
            surname = name_key(strip_paren(ext.display_name))
            if not surname:
                continue
            cands = [p for p in players
                     if _teams_match(p.get('team'), ext.team) and name_key(p['name']).startswith(surname)]
            if not cands:
                continue  # draft-watch に登録されていない選手
            fill_profile(ext)
            if not ext.full_name:
                report.unmatched_profiles.append((ext, cands))
                continue
            exact = [p for p in cands if name_key(p['name']) == name_key(ext.full_name)]
            if len(exact) != 1:
                if len(exact) > 1:
                    report.ambiguous.append((ext, exact))
                continue  # 0人なら同じ名字の別人（draft-watch 未登録）
            player = exact[0]
            warnings = []
            career = player.get('career') or []
            if ext.high_school and career and not any(_hs_match(c, ext.high_school) for c in career):
                warnings.append(f'出身高校が違う？ 連盟={ext.high_school} DB={career}')
            report.matches.append(Match(ext, player, 'name', warnings))
        return report

    def save_links(self, matches: List[Match]) -> int:
        if not self.links_available:
            return 0
        rows = []
        now = datetime.now(timezone.utc).isoformat()
        for m in matches:
            if m.how != 'name':
                continue
            rows.append({
                'player_id': m.player['id'], 'source': m.ext.source, 'ext_key': m.ext.ext_key,
                'ext_name': m.ext.full_name or m.ext.display_name, 'team': m.ext.team,
                'high_school': m.ext.high_school,
                'status': 'candidate' if m.warnings else 'confirmed',
                'note': '; '.join(m.warnings) or None, 'updated_at': now,
            })
        if rows:
            self.sb.table('player_stat_links').upsert(rows, on_conflict='source,ext_key').execute()
        return len(rows)

    # ---- 成績の置き換え ---------------------------------------------------------
    def load_stats(self, player_ids: List[str], year: int, season: str) -> List[Dict]:
        out: List[Dict] = []
        for i in range(0, len(player_ids), 100):
            chunk = player_ids[i:i + 100]
            out.extend(self.sb.table('stats').select('*').in_('player_id', chunk)
                       .eq('year', year).eq('season', season).execute().data or [])
        return out


def is_pitching_row(row: Dict) -> bool:
    return bool((row.get('innings') or 0) > 0 or row.get('era') is not None) and not (row.get('at_bats') or 0)


def wants_batting(player: Dict, ext: ExtPlayer) -> bool:
    """投手専任の選手の打撃行は入れない（打席がある二刀流・野手は入れる）。"""
    if not ext.batting or not ((ext.batting.at_bats or 0) > 0 or (ext.batting.plate_appearances or 0) > 0):
        return False  # 打席に立っていない（守備・代走だけ）の行は入れない
    position = player.get('position') or []
    if isinstance(position, str):
        position = re.split(r'[・/、,]', position)
    position = [x.strip() for x in position if x and x.strip()]
    return not (position and all(x == '投手' for x in position))


@dataclass
class Change:
    player: Dict
    kind: str                   # 'batting' | 'pitching'
    new_row: Dict
    old_rows: List[Dict]
    skipped_locked: bool = False


def plan_changes(store: StatsStore, matches: List[Match], year: int, season: str, tournament: str,
                 source_url_of: Callable[[ExtPlayer], str],
                 is_existing_tournament: Callable[[Optional[str]], bool]) -> List[Change]:
    existing = store.load_stats([m.player['id'] for m in matches], year, season)
    by_player: Dict[str, List[Dict]] = {}
    for row in existing:
        by_player.setdefault(row['player_id'], []).append(row)
    now = datetime.now(timezone.utc).isoformat()
    changes: List[Change] = []
    for m in matches:
        rows = by_player.get(m.player['id'], [])
        league_rows = [r for r in rows if is_existing_tournament(r.get('tournament'))]
        for kind in ('pitching', 'batting'):
            if kind == 'pitching':
                if not m.ext.pitching or not m.ext.pitching.games:
                    continue
                body = pitching_row(m.ext.pitching)
                olds = [r for r in league_rows if is_pitching_row(r)]
            else:
                if not wants_batting(m.player, m.ext):
                    continue
                body = batting_row(m.ext.batting)
                olds = [r for r in league_rows if not is_pitching_row(r)]
            new_row = {
                'player_id': m.player['id'], 'year': year, 'season': season, 'period': 'university',
                'tournament': m.ext.extra.get('tournament', tournament), **body,
                'source': m.ext.source, 'source_url': source_url_of(m.ext), 'fetched_at': now,
                'update_at': now,
            }
            changes.append(Change(m.player, kind, new_row, olds,
                                  skipped_locked=any(r.get('locked') for r in olds)))
    return changes


_COMPARE = ('games', 'at_bats', 'hits', 'home_runs', 'rbis', 'innings', 'strikeouts', 'earned_runs',
            'hits_allowed', 'walks', 'walks_plus_hit_by_pitch', 'batter_strikeouts')


def is_noop(change: Change) -> bool:
    """既存の行と数字が同じで、出典も入っていれば書き換えない。"""
    if len(change.old_rows) != 1:
        return False
    old = change.old_rows[0]
    same = all((old.get(k) or 0) == (change.new_row.get(k) or 0) for k in _COMPARE)
    return same and old.get('source') == change.new_row['source'] and old.get('tournament') == change.new_row['tournament']


def apply_changes(store: StatsStore, changes: List[Change], backup_dir: str, label: str) -> Dict[str, int]:
    todo = [c for c in changes if not c.skipped_locked and not is_noop(c)]
    deleted = [r for c in todo for r in c.old_rows]
    if deleted:
        os.makedirs(backup_dir, exist_ok=True)
        path = os.path.join(backup_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{label}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(deleted, f, ensure_ascii=False, indent=1, default=str)
        ids = [r['id'] for r in deleted]
        for i in range(0, len(ids), 100):
            store.sb.table('stats').delete().in_('id', ids[i:i + 100]).execute()
    rows = [c.new_row for c in todo]
    for i in range(0, len(rows), 200):
        store.sb.table('stats').insert(rows[i:i + 200]).execute()
    return {'inserted': len(rows), 'deleted': len(deleted),
            'locked': sum(1 for c in changes if c.skipped_locked),
            'unchanged': sum(1 for c in changes if is_noop(c))}
