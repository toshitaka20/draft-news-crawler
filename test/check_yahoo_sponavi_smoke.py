#!/usr/bin/env python3
"""
Yahoo!スポーツナビのスクレイピングだけを確認する軽量チェック。
DB、Google Sheets、Gemini APIは呼びません。
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.yahoo_sponavi import fetch_yahoo_sponavi_articles


def main() -> None:
    categories = ["高校野球", "大学野球"]
    max_articles = int(os.getenv("YAHOO_SMOKE_MAX_ARTICLES", "1"))
    total = 0

    print("=== Yahoo!スポーツナビ スモークチェック ===")
    print(f"カテゴリごとの取得数: {max_articles}")

    for category in categories:
        print(f"\n--- {category} ---")
        articles = fetch_yahoo_sponavi_articles(category, max_articles=max_articles)
        total += len(articles)

        print(f"取得記事数: {len(articles)}")
        for i, article in enumerate(articles, 1):
            body_length = len(article.get("body", ""))
            keyword = "あり" if article.get("has_keywords") else "なし"
            print(f"[{i}] {article.get('title', '')}")
            print(f"URL: {article.get('url', '')}")
            print(f"日付: {article.get('date', '')}")
            print(f"本文文字数: {body_length}")
            print(f"キーワード: {keyword}")

    print(f"\n合計取得記事数: {total}")
    if total == 0:
        raise SystemExit("記事を取得できませんでした。Yahoo側の構造変更や通信制限を確認してください。")


if __name__ == "__main__":
    main()
