#!/usr/bin/env python3
"""
すべての記事出力とキーワードフラグ確認テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper.sponichi import fetch_all_sponichi_articles
from scraper.hochi import fetch_hochi_articles
from scraper.nikkan_sports import fetch_all_nikkan_sports_articles
from ai.gemini import process_articles_with_ai
from sheets.google_sheets import update_sheets, get_existing_urls_by_source
from utils import deduplicate_articles
from config import HOCHI_URLS

def test_all_articles_output():
    """すべての記事出力とキーワードフラグ確認テスト"""
    print("=== すべての記事出力とキーワードフラグ確認テスト ===")
    
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
        
        # 5. AIコメント抽出（キーワード記事のみ）
        print("\n5. AIコメント抽出中...")
        processed_articles = process_articles_with_ai(unique_articles)
        print(f"AI処理完了記事数: {len(processed_articles)}")
        
        # 6. Google Sheets更新
        print("\n6. Google Sheets更新中...")
        update_sheets(processed_articles)
        
        print(f"\n=== 処理完了 ===")
        print(f"総記事数: {len(processed_articles)}")
        
        # 結果サマリー
        sources = {}
        keywords_by_source = {}
        for article in processed_articles:
            source = article.get('source', '不明')
            sources[source] = sources.get(source, 0) + 1
            
            if article.get('has_keywords', False):
                keywords_by_source[source] = keywords_by_source.get(source, 0) + 1
        
        print("\n=== ソース別記事数 ===")
        for source, count in sources.items():
            keywords_count = keywords_by_source.get(source, 0)
            print(f"{source}: {count}件 (キーワード: {keywords_count}件)")
        
        # キーワードフラグ確認
        print("\n=== キーワードフラグ確認 ===")
        for i, article in enumerate(processed_articles[:5], 1):
            has_keywords = article.get('has_keywords', False)
            keyword_flag = 'TRUE' if has_keywords else 'FALSE'
            print(f"{i}. {article.get('title', '')[:50]}...")
            print(f"   キーワードフラグ: {keyword_flag}")
            print(f"   スカウトコメント: {article.get('scout_comments', '')[:50]}...")
            print()
        
    except Exception as e:
        print(f"[エラー] テスト失敗: {e}")
        raise

if __name__ == "__main__":
    test_all_articles_output() 