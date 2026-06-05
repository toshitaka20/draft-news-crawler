#!/usr/bin/env python3
"""
既存5社スクレイパーの取得だけを確認する軽量チェック。
DB、Google Sheets、Gemini APIは呼びません。
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.chunichi import fetch_chunichi_articles
from scraper.hochi import fetch_hochi_articles
from scraper.nikkan_sports import fetch_nikkan_sports_articles
from scraper.sanspo import fetch_sanspo_articles
from scraper.sponichi import fetch_sponichi_articles


def main() -> None:
    max_articles = int(os.getenv("REGULAR_SMOKE_MAX_ARTICLES", "1"))
    checks = [
        (
            "スポニチ",
            lambda: fetch_sponichi_articles(
                "https://www.sponichi.co.jp/baseball/tokusyu/highschool/",
                max_articles=max_articles,
                sleep_sec=0,
                category="高校野球",
            ),
        ),
        (
            "スポーツ報知",
            lambda: fetch_hochi_articles(
                "https://hochi.news/tag/%E9%AB%98%E6%A0%A1%E9%87%8E%E7%90%83",
                max_articles=max_articles,
                sleep_sec=0,
                category="高校野球",
            ),
        ),
        (
            "日刊スポーツ",
            lambda: fetch_nikkan_sports_articles(
                "https://www.nikkansports.com/baseball/highschool/atom.xml",
                max_articles=max_articles,
                category="高校野球",
            ),
        ),
        (
            "サンスポ",
            lambda: fetch_sanspo_articles(
                "https://www.sanspo.com/sports/baseball/high/",
                max_articles=max_articles,
                sleep_sec=0,
                category="高校野球",
            ),
        ),
        (
            "中日スポーツ",
            lambda: fetch_chunichi_articles(
                "https://www.chunichi.co.jp/chuspo/baseball/highschool",
                max_articles=max_articles,
                sleep_sec=0,
                category="高校野球",
            ),
        ),
    ]

    print("=== 既存5社 スモークチェック ===")
    print(f"各社の取得数: {max_articles}")

    total = 0
    failures = []

    for source, fetcher in checks:
        print(f"\n--- {source} ---")
        try:
            articles = fetcher()
        except Exception as e:
            print(f"取得エラー: {type(e).__name__}: {e}")
            failures.append(source)
            continue

        total += len(articles)
        print(f"取得記事数: {len(articles)}")
        if not articles:
            failures.append(source)

        for i, article in enumerate(articles, 1):
            body_length = len(article.get("body", ""))
            keyword = "あり" if article.get("has_keywords") else "なし"
            print(f"[{i}] {article.get('title', '')}")
            print(f"URL: {article.get('url', '')}")
            print(f"日付: {article.get('date', '')}")
            print(f"本文文字数: {body_length}")
            print(f"キーワード: {keyword}")

    print(f"\n合計取得記事数: {total}")
    if failures:
        raise SystemExit(f"取得できないソースがあります: {', '.join(failures)}")


if __name__ == "__main__":
    main()
