"""
志望届名簿 ⇄ players の名寄せテスト。

実行: PYTHONPATH=. venv/bin/python3 test/test_pro_aspiring_matching.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.player_matcher import PlayerMatcher, kana_key, name_key, school_key

PLAYERS = [
    {'id': 'p1', 'name': '野崎 健友', 'name_kana': 'のざき けんすけ', 'team': '耐久',
     'category': 'high_school', 'draft_year': 2026, 'declared': False},
    {'id': 'p2', 'name': '高田瑛大', 'name_kana': 'たかだ えいだい', 'team': '都城高',
     'category': 'high_school', 'draft_year': 2026, 'declared': True},
    {'id': 'p3', 'name': '吉川 凌平', 'name_kana': 'よしかわ りょうへい', 'team': '千葉商科大',
     'category': 'university', 'draft_year': 2026, 'declared': True},
    # 同姓同名（別大学・別学年）。学校で絞れれば一意、絞れなければ判定保留にする。
    {'id': 'p4', 'name': '佐藤 大介', 'name_kana': 'さとう だいすけ', 'team': '常葉大菊川',
     'category': 'high_school', 'draft_year': 2026, 'declared': True},
    {'id': 'p5', 'name': '佐藤 大介', 'name_kana': 'さとう だいすけ', 'team': '東北福祉大',
     'category': 'university', 'draft_year': 2027, 'declared': True},
    {'id': 'p7', 'name': '佐藤 大介', 'name_kana': 'さとう だいすけ', 'team': '横浜',
     'category': 'high_school', 'draft_year': 2026, 'declared': True},
    # ふりがなでしか一致しないケース（DB側の漢字表記が違う）
    {'id': 'p6', 'name': '斉藤 颯', 'name_kana': 'さいとう はやて', 'team': '関根学園',
     'category': 'high_school', 'draft_year': 2026, 'declared': False},
]


def entry(name, school, category='high_school', kana=None):
    return {'name': name, 'school': school, 'category': category, 'name_kana': kana}


def check(label, condition):
    print(('  OK   ' if condition else '  FAIL ') + label)
    return condition


def main() -> int:
    ok = True
    matcher = PlayerMatcher([dict(p) for p in PLAYERS])

    print('キー正規化')
    ok &= check('異体字: 野﨑 == 野崎', name_key('野﨑 健友') == name_key('野崎 健友'))
    ok &= check('異体字: 髙田 == 高田', name_key('髙田 瑛大') == name_key('高田 瑛大'))
    ok &= check('異体字: 當山 == 当山', name_key('當山 航大') == name_key('当山 航大'))
    ok &= check('空白: 全角/半角/なし', name_key('高田　瑛大') == name_key('高田 瑛大') == name_key('高田瑛大'))
    ok &= check('かな: カタカナ==ひらがな', kana_key('ヨシカワ リョウヘイ') == kana_key('よしかわ　りょうへい'))
    ok &= check('学校: 千葉商科大学 == 千葉商科大', school_key('千葉商科大学') == school_key('千葉商科大'))
    ok &= check('学校: 金沢学院大附 == 金沢学院大付', school_key('金沢学院大附') == school_key('金沢学院大付'))

    print('\n名寄せ')
    result = matcher.match(entry('野﨑 健友', '耐久'), draft_year=2026)
    ok &= check('異体字ちがいでも一致する', result.status == 'matched' and result.player['id'] == 'p1')

    result = matcher.match(entry('高田 瑛大', '都城'), draft_year=2026)
    ok &= check('学校の「高」有無を吸収して一致する', result.status == 'matched' and result.player['id'] == 'p2')

    result = matcher.match(entry('佐藤 大介', '常葉大菊川'), draft_year=2026)
    ok &= check('同姓同名は学校で一意に決まる', result.status == 'matched' and result.player['id'] == 'p4')

    result = matcher.match(entry('佐藤 大介', '名簿にない高'), draft_year=2026)
    ok &= check('学校で絞れない同姓同名は自動更新せず判定保留にする',
                result.status == 'ambiguous' and {c['id'] for c in result.candidates} == {'p4', 'p7'})

    result = matcher.match(
        entry('齊藤 颯', '関根学園', kana='さいとう はやて'), draft_year=2026)
    ok &= check('漢字が違ってもふりがなで一致する',
                result.status == 'matched' and result.player['id'] == 'p6')

    result = matcher.match(entry('存在 しない', '架空高'), draft_year=2026)
    ok &= check('未登録は unmatched', result.status == 'unmatched')

    result = matcher.match(entry('野崎 健介', '耐久'), draft_year=2026)
    ok &= check('同校の似た名前は候補として提示する（自動リンクはしない）',
                result.status == 'unmatched' and any(s['id'] == 'p1' for s in result.suggestions))

    result = matcher.match(entry('吉川 凌平', '千葉商科大学', category='university',
                                 kana='よしかわ りょうへい'), draft_year=2026)
    ok &= check('大学名の「大学/大」ゆれを吸収して一致する',
                result.status == 'matched' and result.player['id'] == 'p3')

    print('\n' + ('すべて成功' if ok else '失敗あり'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
