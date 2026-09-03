"""
公開記事の部分更新テスト。人が書いた文章を壊さずに、表と人数・日付だけ差し替えられるかを見る。

実行: PYTHONPATH=. venv/bin/python3 test/test_pro_aspiring_article.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pro_aspiring_site_article import update_article_content, update_article_meta

ARTICLE = """\
リード文です。**9月3日時点の提出者は高校生2人・大学生1人の合計3人**です。

## プロ志望届とは

人が書いた解説。ここは絶対に触ってはいけない。

## 高校生のプロ志望届 提出者一覧（2人）

| 都道府県 | 学校 | 選手 | ポジション | 評価 | 受付日 |
|---|---|---|---|---|---|
| 北海道 | 小樽双葉 | 近藤 琉唯斗 | 投手 | E | 8月25日 |
| 青森 | 八戸学院光星 | 北口 晃大 | 投手 | E | 8月25日 |

※注記です（2026年9月3日午後5時時点）。この文も残る。

## 大学生のプロ志望届 提出者一覧（1人）

| 連盟 | 大学 | 選手 | ポジション | 評価 | 受付日 |
|---|---|---|---|---|---|
| 東都大学 | 順天堂大学 | 衛藤 航太朗 | — | — | 9月2日 |

※大学の注記。

## まだ提出していない主な上位候補

Draft-Watchで上位評価（B以上）を付けている選手のうち、9月3日時点で一覧に名前が無い高校生は1人、大学生は0人です。

### 高校生

| 評価 | 選手 | 所属 | ポジション |
|---|---|---|---|
| S | 織田 翔希 | 横浜高校 | 投手 |

人が書いた解説2。

### 大学生

| 評価 | 選手 | 所属 | ポジション |
|---|---|---|---|
| S | 渡部 海 | 青山学院大 | 捕手 |

## まとめ

人が書いた締めの文章。
"""

PLAYERS = [
    {'id': 'p1', 'name': '近藤 琉唯斗', 'team': '小樽双葉', 'category': 'high_school',
     'draft_year': 2026, 'rank': 40, 'position': ['投手']},
    {'id': 'p2', 'name': '北口 晃大', 'team': '八戸学院光星', 'category': 'high_school',
     'draft_year': 2026, 'rank': 40, 'position': ['投手']},
    {'id': 'p3', 'name': '末吉 良丞', 'team': '沖縄尚学', 'category': 'high_school',
     'draft_year': 2026, 'rank': 70, 'position': ['投手']},
    {'id': 'p4', 'name': '織田 翔希', 'team': '横浜高校', 'category': 'high_school',
     'draft_year': 2026, 'rank': 90, 'position': ['投手']},
    {'id': 'p5', 'name': '渡部 海', 'team': '青山学院大', 'category': 'university',
     'draft_year': 2026, 'rank': 90, 'position': ['捕手']},
]

RECORDS = [
    {'category': 'high_school', 'affiliation': '北海道', 'school': '小樽双葉',
     'name': '近藤 琉唯斗', 'received_date': '8月25日', 'player_id': 'p1', 'draft_eligible': True},
    {'category': 'high_school', 'affiliation': '青森', 'school': '八戸学院光星',
     'name': '北口 晃大', 'received_date': '8月25日', 'player_id': 'p2', 'draft_eligible': True},
    # 新しく提出した選手（未提出リストから消えるはず）
    {'category': 'high_school', 'affiliation': '沖縄', 'school': '沖縄尚学',
     'name': '末吉 良丞', 'received_date': '9月4日', 'player_id': 'p3', 'draft_eligible': True},
    # 未登録の選手（リンクなしで載る）
    {'category': 'high_school', 'affiliation': '兵庫', 'school': '松陰',
     'name': '松田 陽希', 'received_date': '9月4日', 'player_id': None, 'draft_eligible': True},
    {'category': 'university', 'affiliation': '東都大学野球連盟', 'school': '順天堂大学',
     'name': '衛藤 航太朗', 'received_date': '9月2日', 'player_id': None, 'draft_eligible': True},
]

COUNTS = {'high_school': 4, 'university': 1, 'university_ineligible': 0,
          'matched': 3, 'unmatched': 2, 'ambiguous': 0}


def check(label, condition):
    print(('  OK   ' if condition else '  FAIL ') + label)
    return condition


def main() -> int:
    ok = True
    updated, blocks = update_article_content(
        ARTICLE, RECORDS, PLAYERS, 2026, datetime(2026, 9, 4, 9, 30), COUNTS)

    print('本文の部分更新')
    ok &= check('人が書いた文章が残る',
                '人が書いた解説。ここは絶対に触ってはいけない。' in updated
                and '人が書いた解説2。' in updated
                and '人が書いた締めの文章。' in updated)
    ok &= check('注記が残り、時点だけ更新される',
                '※注記です（2026年9月4日9時30分時点）。この文も残る。' in updated
                and '※大学の注記。' in updated)
    ok &= check('リードの人数が更新される',
                '**9月4日時点の提出者は高校生4人・大学生1人の合計5人**' in updated)
    ok &= check('見出しの人数が更新される',
                '## 高校生のプロ志望届 提出者一覧（4人）' in updated)
    ok &= check('新しい提出者が表に入る', '| 沖縄 | 沖縄尚学 |' in updated)
    ok &= check('未登録選手はリンクなしで載る', '| 兵庫 | 松陰 | 松田 陽希 | — | — | 9月4日 |' in updated)
    ok &= check('登録選手は選手ページへリンクする',
                '[近藤 琉唯斗](https://draft-watch.com/players/2026/p1)' in updated)
    ok &= check('連盟名から「野球連盟」が落ちる', '| 東都大学 | 順天堂大学 |' in updated)
    ok &= check('提出済みの選手は未提出リストから消える',
                updated.count('末吉 良丞') == 1)
    ok &= check('未提出の人数が更新される',
                '9月4日時点で一覧に名前が無い高校生は1人、大学生は1人です' in updated)
    ok &= check('更新ブロックが全部拾えている', len(blocks) == 7)

    print('\n見出しが無いときは触らない')
    stripped = ARTICLE.replace('## 高校生のプロ志望届 提出者一覧（2人）', '## 高校生のみなさん')
    result, _ = update_article_content(
        stripped, RECORDS, PLAYERS, 2026, datetime(2026, 9, 4, 9, 30), COUNTS)
    ok &= check('見出しが変わったセクションの表は元のまま',
                '| 北海道 | 小樽双葉 | 近藤 琉唯斗 | 投手 | E | 8月25日 |' in result)

    print('\nタイトル・抜粋の更新')
    meta = update_article_meta(
        {'title': '【ドラフト2026】プロ志望届 提出者一覧（9月3日時点）高校生2人・大学生1人｜注目選手',
         'excerpt': 'まとめます。9月3日時点は高校生2人・大学生1人の計3人。締切は10月8日です。'},
        COUNTS, datetime(2026, 9, 4, 9, 30))
    ok &= check('タイトルの日付と人数が更新される',
                meta['title'] == '【ドラフト2026】プロ志望届 提出者一覧（9月4日時点）'
                                 '高校生4人・大学生1人｜注目選手')
    ok &= check('抜粋の日付と人数が更新される',
                meta['excerpt'] == 'まとめます。9月4日時点は高校生4人・大学生1人の計5人。締切は10月8日です。')

    print('\n' + ('すべて成功' if ok else '失敗あり'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
