"""球歴.com の試合記録で、連盟が出していない項目を補う（今は首都大学野球連盟だけ）。

首都の公式記録は打撃が打数・安打・打点、投手が投球回・被安打・自責しか出ていないので、
三振・四死球・盗塁（打撃）と奪三振・与四死球（投手）を球歴の試合ごとの記録を足し上げて埋める。

- 球歴の記録は利用者の投稿なので、連盟の公式記録と食い違うことがある（試合が抜けているなど）。
  そこで、公式記録にもある打数（投手はアウト数）が球歴の足し上げと一致し、安打（被安打）の差が
  1以内の選手だけ、空いている項目を埋める。一致しない選手は空けたまま、理由を表示する。
- 公式記録にある数字は上書きしない（連盟の数字が正）。
- 取得は球歴の公開API（大会の試合一覧と、試合ごとの選手記録）を1件ずつ間をあけて読む。
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from database.player_matcher import name_key
from stats_sync.common import ExtPlayer, fetch_json, innings_outs
from stats_sync.store import _hs_match

API = 'https://www.kyureki.com/api/v1/game/'

# 球歴の大会ID（首都の部ごと）。新しいシーズンは https://www.kyureki.com/univ/game/s{番号}/ の一覧で探して足す
SHUTO_TAIKAI: Dict[Tuple[int, str], Dict[str, str]] = {
    (2026, 'spring'): {'1': '67347', '2': '67714'},
    (2026, 'fall'): {'1': '68196', '2': '68209'},
}


@dataclass
class KyurekiLine:
    team: str
    name: str
    high_school: Optional[str]
    bat_games: int = 0
    at_bats: int = 0
    hits: int = 0
    rbis: int = 0
    strikeouts: int = 0
    walks_hbp: int = 0
    steals: int = 0
    pit_games: int = 0
    outs: int = 0
    hits_allowed: int = 0
    p_strikeouts: int = 0
    p_walks_hbp: int = 0
    earned_runs: int = 0
    gids: List[str] = field(default_factory=list)


def _i(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _high_school(member: Dict) -> Optional[str]:
    schools = [k.get('team') for k in member.get('kyureki_list') or [] if k.get('category') == '高校']
    return schools[-1] if schools else None


def league_games(taikai_id: str) -> List[Dict]:
    """大会の試合一覧（日付順）。同じ試合の重複登録と、勝ち点が決まった後の対戦（3勝目以降）は除く。"""
    games = fetch_json(API + 'game_list.php',
                       {'type': 'taikai_game', 'taikai_id': taikai_id, 'version': 1, 'consistent': 1})
    games = sorted(games, key=lambda g: (g.get('date') or '', g.get('gid') or ''))
    seen: Dict[Tuple, Dict] = {}
    for g in games:
        key = (g.get('date'), frozenset((g.get('team1'), g.get('team2'))),
               frozenset(((g.get('team1'), g.get('team1_ten')), (g.get('team2'), g.get('team2_ten')))))
        # 重複は選手記録（スタメン）があるほうを残す
        if key not in seen or (str(seen[key].get('stamen_flag')) == '0' and str(g.get('stamen_flag')) != '0'):
            seen[key] = g
    wins: Dict[frozenset, Counter] = {}
    kept = []
    for g in sorted(seen.values(), key=lambda g: (g.get('date') or '', g.get('gid') or '')):
        pair = frozenset((g['team1'], g['team2']))
        w = wins.setdefault(pair, Counter())
        if max(w.values(), default=0) >= 2:
            continue
        kept.append(g)
        r1, r2 = _i(g.get('team1_ten')), _i(g.get('team2_ten'))
        if r1 != r2:
            w[g['team1'] if r1 > r2 else g['team2']] += 1
    return kept


def season_lines(taikai_id: str, canonical_team) -> Tuple[Dict[Tuple[str, str], KyurekiLine], List[str]]:
    """大会の全試合の選手記録を (大学, フルネーム) ごとに足し上げる。"""
    acc: Dict[Tuple[str, str], KyurekiLine] = {}
    notes: List[str] = []
    for g in league_games(taikai_id):
        data = fetch_json(API + 'game.php', {'id': g['gid'], 'stats_flag': 'true'})
        game = data[0] if isinstance(data, list) and data else {}
        members = game.get('game_member') or []
        teams = [canonical_team(t.get('team') or '') for t in game.get('teams') or []]
        if len(members) != 2 or len(teams) != 2 or not any(members):
            notes.append(f'選手記録のない試合: {g.get("date")} {g.get("team1")}-{g.get("team2")}（{g["gid"]}）')
            continue
        for team, rows in zip(teams, members):
            for m in rows or []:
                name = (m.get('name') or '').strip()
                if not name:
                    continue
                line = acc.setdefault((team, name), KyurekiLine(team, name, _high_school(m)))
                line.gids.append(g['gid'])
                if 1 <= _i(m.get('jun')) <= 9:
                    line.bat_games += 1
                    line.at_bats += _i(m.get('dasuu'))
                    line.hits += _i(m.get('hit'))
                    line.rbis += _i(m.get('daten'))
                    line.strikeouts += _i(m.get('sanshin'))
                    line.walks_hbp += _i(m.get('fourball'))
                    line.steals += _i(m.get('tourui'))
                if _i(m.get('pno')) > 0:
                    line.pit_games += 1
                    line.outs += _i(m.get('toukyukai')) * 3 + _i(m.get('toukyukai_m'))
                    line.hits_allowed += _i(m.get('hianda'))
                    line.p_strikeouts += _i(m.get('datsusanshin'))
                    line.p_walks_hbp += _i(m.get('pfourball'))
                    line.earned_runs += _i(m.get('zisekiten'))
    return acc, notes


def _find(ext: ExtPlayer, lines: Dict[Tuple[str, str], KyurekiLine]) -> List[KyurekiLine]:
    short = name_key(ext.full_name or ext.display_name)
    cands = [l for (team, _), l in lines.items()
             if team == ext.team and name_key(l.name).startswith(short)]
    if len(cands) > 1 and ext.high_school:
        cands = [l for l in cands if _hs_match(l.high_school, ext.high_school)]
    return cands


def supplement_shuto(year: int, season: str, players: List[ExtPlayer], canonical_team) -> List[str]:
    """首都の選手の空いている項目を球歴の足し上げで埋める。表示用のメッセージを返す。"""
    taikai = SHUTO_TAIKAI.get((year, season))
    if not taikai:
        return [f'球歴の大会IDが未登録です（{year} {season}）。stats_sync/kyureki.py の SHUTO_TAIKAI に足してください']
    messages: List[str] = []
    filled = mismatched = missing = 0
    for div, taikai_id in taikai.items():
        try:
            lines, notes = season_lines(taikai_id, canonical_team)
        except Exception as e:  # 球歴が読めなくても、連盟の記録の取り込みは続ける
            messages.append(f'球歴を読めません（{div}部）: {e}')
            continue
        messages.extend(notes)
        tournament = f'首都{div}部'
        for ext in players:
            if ext.extra.get('tournament') != tournament:
                continue
            cands = _find(ext, lines)
            if len(cands) != 1:
                missing += 1
                if cands or (ext.batting and ext.batting.at_bats) or (ext.pitching and ext.pitching.innings):
                    messages.append(f'球歴で特定できない: {ext.display_name}（{ext.team}・{ext.high_school}）'
                                    f' 候補{len(cands)}人')
                continue
            # 同じ大学で名前の先頭が合うのが1人なら同一人物とみなす（出身校は「県立相模原/県相模原」
            # 「日本学園/明治大世田谷」のように書き方や校名変更で揃わないことが多いので、決め手にしない）
            k = cands[0]
            ext.extra['kyureki_name'] = k.name
            ok = True
            b = ext.batting
            if b and b.at_bats:
                # 安打/失策・打点は記録員の判断でずれることがあるので、打数が一致して安打の差が1以内なら
                # 同じ試合を数えたとみなす（試合が抜けていれば打数がずれる）
                official = (b.at_bats, b.hits, b.rbis)
                mine = (k.at_bats, k.hits, k.rbis)
                if official[0] == mine[0] and abs((official[1] or 0) - mine[1]) <= 1:
                    if b.strikeouts is None:
                        b.strikeouts = k.strikeouts
                    if b.walks is None:
                        b.walks, b.hit_by_pitch = k.walks_hbp, 0   # 球歴は四死球の合計しかない
                    if b.steals is None:
                        b.steals = k.steals
                else:
                    ok = False
                    messages.append(f'打撃が公式と違うので補わない: {k.name}（{ext.team}）'
                                    f' 公式(打数,安打,打点)={official} 球歴={mine}')
            p = ext.pitching
            if p and p.innings:
                official = (innings_outs(p.innings), p.hits_allowed, p.earned_runs)
                mine = (k.outs, k.hits_allowed, k.earned_runs)
                same_k = p.strikeouts is None or abs(p.strikeouts - k.p_strikeouts) <= 1
                # 被安打・自責点も判断で変わりうるので、アウト数が一致して被安打の差が1以内なら補う
                if official[0] == mine[0] and abs((official[1] or 0) - mine[1]) <= 1 and same_k:
                    if p.strikeouts is None:
                        p.strikeouts = k.p_strikeouts
                    if p.walks_plus_hbp is None:
                        p.walks_plus_hbp = k.p_walks_hbp
                else:
                    ok = False
                    messages.append(f'投球が公式と違うので補わない: {k.name}（{ext.team}）'
                                    f' 公式(アウト,被安打,自責)={official} 球歴={mine}'
                                    + ('' if same_k else f' 奪三振 公式={p.strikeouts} 球歴={k.p_strikeouts}'))
            if ok:
                filled += 1
            else:
                mismatched += 1
    messages.insert(0, f'球歴で補えた選手 {filled}人・公式と違うので補わなかった {mismatched}人・特定できない {missing}人')
    return messages
