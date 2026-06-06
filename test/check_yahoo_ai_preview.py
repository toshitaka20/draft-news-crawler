#!/usr/bin/env python3
"""
Yahoo!スポーツナビの記事にAI抽出だけを実行するプレビュー。
DB保存・Google Sheets更新は行わない。
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.gemini import process_articles_with_ai, process_player_candidates_with_ai
from config import YAHOO_SPONAVI_MAX_ARTICLES, YAHOO_SPONAVI_URLS
from scraper.yahoo_sponavi import YahooSponaviScraper
from utils import annotate_article_signals


def main() -> None:
    print("=== Yahoo AI preview: no DB / no Sheets ===")
    scraper = YahooSponaviScraper()
    all_articles = []

    for category, _url in YAHOO_SPONAVI_URLS.items():
        print(f"\n=== {category}記事取得中 ===")
        articles = scraper.fetch_article_list(
            category=category,
            max_articles=YAHOO_SPONAVI_MAX_ARTICLES,
            exclude_urls=set(),
        )

        detailed = []
        for article in articles:
            if not article.get("url"):
                continue

            title, date, body = scraper.fetch_article_content(article["url"])
            if not title or not body:
                print(f"[SKIP] 本文取得失敗: {article.get('url', '')}")
                continue

            article["title"] = title
            article["body"] = body
            article["date"] = date or article.get("date", "")
            annotate_article_signals(article)
            detailed.append(article)

        print(f"{category}: {len(detailed)}件")
        all_articles.extend(detailed)

    print(f"\n取得記事数: {len(all_articles)}件")
    for i, article in enumerate(all_articles, 1):
        print(
            f"[{i}] scout={article.get('has_scout_comment_candidate')} "
            f"attention={article.get('has_attention_candidate')} "
            f"player={article.get('has_player_candidate')} "
            f"title={article.get('title', '')[:80]}"
        )

    scout_targets = [
        article
        for article in all_articles
        if article.get("has_scout_comment_candidate", False)
    ]
    non_scout = [
        article
        for article in all_articles
        if not article.get("has_scout_comment_candidate", False)
    ]
    print(f"\nスカウトコメントAI対象: {len(scout_targets)}件")

    processed_scout = process_articles_with_ai(scout_targets) if scout_targets else []
    for article in non_scout:
        article["scout_comments"] = "スカウトコメント候補なし"
        article["scout_rows"] = []

    processed = processed_scout + non_scout
    player_target_count = sum(
        1 for article in processed if article.get("has_player_candidate", False)
    )
    print(f"\n選手候補AI対象: {player_target_count}件")
    processed = process_player_candidates_with_ai(processed)

    print("\n=== AI Preview Results ===")
    for i, article in enumerate(processed, 1):
        scout_rows = article.get("scout_rows", [])
        player_rows = article.get("player_candidate_rows", [])
        attention_rows = article.get("attention_rows", [])
        if not scout_rows and not player_rows and not attention_rows:
            continue

        print(f"\n--- #{i} {article.get('title', '')}")
        print(f"URL: {article.get('url', '')}")
        print(
            f"Date: {article.get('date', '')} "
            f"Source: {article.get('source', '')} "
            f"Category: {article.get('category', '')}"
        )
        print(
            f"Flags: scout={article.get('has_scout_comment_candidate')} "
            f"attention={article.get('has_attention_candidate')} "
            f"player={article.get('has_player_candidate')}"
        )

        if attention_rows:
            print(f"Attention rows ({len(attention_rows)}):")
            for row in attention_rows:
                print(
                    f"  team_count={row[5]} person_count={row[6]} "
                    f"teams={row[7]} npb={row[8]} mlb={row[9]} "
                    f"score={row[10]} evidence={row[11]}"
                )

        if scout_rows:
            print(f"Scout rows ({len(scout_rows)}):")
            for row in scout_rows:
                print("  " + " | ".join(str(value) for value in row))

        if player_rows:
            print(f"Player candidates ({len(player_rows)}):")
            for row in player_rows:
                print(
                    f"  name={row.get('name')} team={row.get('team_name')} "
                    f"year={row.get('school_year')} pos={row.get('position')} "
                    f"conf={row.get('confidence')} evidence={row.get('evidence')}"
                )

    print("\n=== Summary ===")
    print(f"articles={len(processed)}")
    print(f"attention_rows={sum(len(a.get('attention_rows', [])) for a in processed)}")
    print(f"scout_rows={sum(len(a.get('scout_rows', [])) for a in processed)}")
    print(
        "player_candidate_rows="
        f"{sum(len(a.get('player_candidate_rows', [])) for a in processed)}"
    )


if __name__ == "__main__":
    main()
