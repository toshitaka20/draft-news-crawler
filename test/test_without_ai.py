#!/usr/bin/env python3
"""
スカウトコメント抽出なしでテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper.sponichi import fetch_all_sponichi_articles
from scraper.hochi import fetch_hochi_articles
from scraper.nikkan_sports import fetch_all_nikkan_sports_articles
from sheets.google_sheets import update_sheets, get_existing_urls_by_source
from utils import deduplicate_articles
from config import HOCHI_URLS

def test_without_ai():
    """スカウトコメント抽出なしでテスト"""
    print("=== スカウトコメント抽出なしテスト ===")
    
    all_articles = []
    
    try:
        # 1. スポニチ記事取得
        print("\n1. スポニチ記事取得中...")
        sponichi_existing_urls = get_existing_urls_by_source('スポニチ')
        sponichi_articles = fetch_all_sponichi_articles(exclude_urls=sponichi_existing_urls)
        all_articles.extend(sponichi_articles)
        print(f"スポニチ記事数: {len(sponichi_articles)}")
        
        # キーワードフラグ確認
        sponichi_keywords = sum(1 for a in sponichi_articles if a.get('has_keywords', False))
        print(f"スポニチキーワード記事数: {sponichi_keywords}")
        
        # 2. スポーツ報知記事取得
        print("\n2. スポーツ報知記事取得中...")
        hochi_existing_urls = get_existing_urls_by_source('スポーツ報知')
        hochi_articles = []
        for category, url in HOCHI_URLS.items():
            print(f"  {category}記事取得中...")
            category_articles = fetch_hochi_articles(url, exclude_urls=hochi_existing_urls, category=category)
            hochi_articles.extend(category_articles)
        all_articles.extend(hochi_articles)
        print(f"スポーツ報知記事数: {len(hochi_articles)}")
        
        # キーワードフラグ確認
        hochi_keywords = sum(1 for a in hochi_articles if a.get('has_keywords', False))
        print(f"スポーツ報知キーワード記事数: {hochi_keywords}")
        
        # 3. 日刊スポーツ記事取得
        print("\n3. 日刊スポーツ記事取得中...")
        nikkan_existing_urls = get_existing_urls_by_source('日刊スポーツ')
        nikkan_articles = fetch_all_nikkan_sports_articles(exclude_urls=nikkan_existing_urls)
        all_articles.extend(nikkan_articles)
        print(f"日刊スポーツ記事数: {len(nikkan_articles)}")
        
        # キーワードフラグ確認
        nikkan_keywords = sum(1 for a in nikkan_articles if a.get('has_keywords', False))
        print(f"日刊スポーツキーワード記事数: {nikkan_keywords}")
        
        # 4. 重複除去
        print("\n4. 重複除去中...")
        unique_articles = deduplicate_articles(all_articles)
        print(f"重複除去後記事数: {len(unique_articles)}")
        
        # 5. AI処理をスキップしてスカウトコメントを空にする
        print("\n5. AI処理スキップ中...")
        for article in unique_articles:
            article['scout_comments'] = "AI処理スキップ"
            article['scout_rows'] = []  # 空のスカウト行
        
        # 6. Google Sheets更新
        print("\n6. Google Sheets更新中...")
        update_sheets(unique_articles)
        
        print(f"\n=== 処理完了 ===")
        print(f"総記事数: {len(unique_articles)}")
        
        # 結果サマリー
        sources = {}
        keywords_by_source = {}
        categories = {}
        for article in unique_articles:
            source = article.get('source', '不明')
            sources[source] = sources.get(source, 0) + 1
            
            if article.get('has_keywords', False):
                keywords_by_source[source] = keywords_by_source.get(source, 0) + 1
            
            category = article.get('category', '不明')
            categories[category] = categories.get(category, 0) + 1
        
        print("\n=== ソース別記事数 ===")
        for source, count in sources.items():
            keywords_count = keywords_by_source.get(source, 0)
            print(f"{source}: {count}件 (キーワード: {keywords_count}件)")
        
        print("\n=== カテゴリ別記事数 ===")
        for category, count in categories.items():
            print(f"{category}: {count}件")
        
        # キーワードフラグ確認
        print("\n=== キーワードフラグ確認 ===")
        for i, article in enumerate(unique_articles[:5], 1):
            has_keywords = article.get('has_keywords', False)
            keyword_flag = 'TRUE' if has_keywords else 'FALSE'
            print(f"{i}. {article.get('title', '')[:50]}...")
            print(f"   カテゴリ: {article.get('category', '')}")
            print(f"   キーワードフラグ: {keyword_flag}")
            print(f"   スカウトコメント: {article.get('scout_comments', '')}")
            print()
        
    except Exception as e:
        print(f"[エラー] テスト失敗: {e}")
        raise

if __name__ == "__main__":
    test_without_ai() 