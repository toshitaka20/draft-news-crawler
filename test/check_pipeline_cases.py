#!/usr/bin/env python3
"""
記事シグナル判定と crawled_articles 保存の回帰チェック。
Gemini APIは呼びません。
"""

import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import get_existing_crawled_urls_by_source, upsert_crawled_articles
from utils import annotate_article_signals


CASES = [
    {
        "name": "rakuten_scout_comment",
        "expected_scout": True,
        "expected_attention": True,
        "expected_player": True,
        "title": "愛工大・プロ注目の最速152キロ右腕、8回無失点の快投 楽天スカウト「ストライク先行で緩急も。今後が楽しみ」",
        "body": (
            "愛工大が名城大に3―0で勝った。プロ注目の最速152キロ右腕・岡田雅樹投手"
            "（4年・愛知商）が8イニングを5安打無失点に抑えた。バックネット裏では"
            "5球団のスカウトが視察しており、楽天の益田スカウトは「先発では初めて見るが、"
            "ストライク先行で緩急も使えている。今後が楽しみ」と話した。"
        ),
    },
    {
        "name": "cbo_comment_12_teams",
        "expected_scout": True,
        "expected_attention": True,
        "expected_player": True,
        "title": "栗山CBOも来た！全12球団の前で立命大・有馬伽久が完投星",
        "body": (
            "米沢との投げ合いにNPB12球団24人のスカウトが集結し、8球団が複数人態勢を"
            "敷く注目の一戦だった。最多4人を配置した日本ハムは、栗山英樹CBOが現地視察し、"
            "「どのチームも左腕は気になる。いい投手であることは間違いない」と言及した。"
        ),
    },
    {
        "name": "front_office_comment_multi_sentence",
        "expected_scout": True,
        "expected_attention": True,
        "expected_player": True,
        "title": "関大・米沢友翔、スカウト12球団47人の前で快投",
        "body": (
            "ネット裏にはNPB12球団47人が集結。巨人は水野雄仁編成本部長、長野久義編成本部参与ら"
            "異例の11人が視察。巨人・水野編成本部長は「関西を代表する左右の素晴らしい投手の対決。"
            "真っすぐも変化球も、うまく操っていた。負けられない試合で結果を出すのは投手として"
            "評価できる」と称賛した。"
        ),
    },
    {
        "name": "manager_only_should_skip",
        "expected_scout": False,
        "expected_attention": False,
        "expected_player": False,
        "title": "高校監督がエースを称賛",
        "body": "高校の佐藤監督は「よく投げた。成長した」と話した。選手本人も「次も頑張る」と語った。",
    },
    {
        "name": "ob_comment_should_skip",
        "expected_scout": False,
        "expected_attention": False,
        "expected_player": False,
        "title": "解説者が大学生投手を評価",
        "body": "解説者の栗山英樹氏は「いい投手だと思う」と話した。球団視察の記述はない。",
    },
    {
        "name": "attention_only_no_comment",
        "expected_scout": False,
        "expected_attention": True,
        "expected_player": True,
        "title": "ドラフト候補対決に12球団が集結",
        "body": "ドラフト候補対決にNPB12球団32人が集結した。スカウトの具体的なコメントはなかった。",
    },
]


def build_article(case):
    article = {
        "source": "テスト",
        "category": "回帰テスト",
        "url": f"https://example.com/pipeline-test/{case['name']}",
        "title": case["title"],
        "body": case["body"],
        "date": "2026-06-07 12:00",
    }
    annotate_article_signals(article)
    return article


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", action="store_true", help="crawled_articlesへupsertする")
    args = parser.parse_args()

    articles = []
    failures = []

    for case in CASES:
        article = build_article(case)
        articles.append(article)
        scout = article["has_scout_comment_candidate"]
        attention = article["has_attention_candidate"]
        player = article["has_player_candidate"]
        print(f"\n[{case['name']}]")
        print(f"  scout_candidate: {scout} expected={case['expected_scout']}")
        print(f"  attention_candidate: {attention} expected={case['expected_attention']}")
        print(f"  player_candidate: {player} expected={case['expected_player']}")
        print(f"  attention_rows: {len(article.get('attention_rows', []))}")
        for row in article.get("attention_rows", []):
            print(f"    row: team_count={row[5]} person_count={row[6]} teams={row[7]} score={row[10]}")

        if (
            scout != case["expected_scout"]
            or attention != case["expected_attention"]
            or player != case["expected_player"]
        ):
            failures.append(case["name"])

    if args.db:
        before = get_existing_crawled_urls_by_source("テスト")
        result = upsert_crawled_articles(articles)
        after = get_existing_crawled_urls_by_source("テスト")
        urls = {article["url"] for article in articles}
        print("\n[DB]")
        print(f"  before_matches: {len(before & urls)}")
        print(f"  upsert_result: {result}")
        print(f"  after_matches: {len(after & urls)}")
        if result["errors"] or len(after & urls) != len(urls):
            failures.append("db_upsert")

    if failures:
        raise SystemExit(f"failed cases: {', '.join(failures)}")

    print("\nOK")


if __name__ == "__main__":
    main()
