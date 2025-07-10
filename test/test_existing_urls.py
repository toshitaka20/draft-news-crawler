#!/usr/bin/env python3
"""
既存URL除外機能の動作確認テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sheets.google_sheets import get_existing_urls_by_source
from scraper.sponichi import fetch_all_sponichi_articles
from scraper.hochi import fetch_hochi_articles
from scraper.nikkan_sports import fetch_all_nikkan_sports_articles
from config import HOCHI_URLS

def test_existing_urls_functionality():
    """既存URL除外機能の動作確認"""
    print("=== 既存URL除外機能の動作確認 ===")
    
    try:
        # 1. 既存URL取得テスト
        print("\n1. 既存URL取得テスト")
        sponichi_existing = get_existing_urls_by_source('スポニチ')
        hochi_existing = get_existing_urls_by_source('スポーツ報知')
        nikkan_existing = get_existing_urls_by_source('日刊スポーツ')
        
        print(f"スポニチ既存URL数: {len(sponichi_existing)}")
        print(f"スポーツ報知既存URL数: {len(hochi_existing)}")
        print(f"日刊スポーツ既存URL数: {len(nikkan_existing)}")
        
        if sponichi_existing:
            print(f"スポニチ既存URL例: {list(sponichi_existing)[:3]}")
        if hochi_existing:
            print(f"スポーツ報知既存URL例: {list(hochi_existing)[:3]}")
        if nikkan_existing:
            print(f"日刊スポーツ既存URL例: {list(nikkan_existing)[:3]}")
        
        # 2. スポニチ記事取得テスト（既存URL除外）
        print("\n2. スポニチ記事取得テスト（既存URL除外）")
        sponichi_articles = fetch_all_sponichi_articles(exclude_urls=sponichi_existing)
        print(f"スポニチ取得記事数: {len(sponichi_articles)}")
        
        if sponichi_articles:
            print("スポニチ記事例:")
            for i, article in enumerate(sponichi_articles[:3]):
                print(f"  {i+1}. {article.get('title', '')}")
                print(f"     URL: {article.get('url', '')}")
        
        # 3. スポーツ報知記事取得テスト（既存URL除外）
        print("\n3. スポーツ報知記事取得テスト（既存URL除外）")
        hochi_articles = []
        for category, url in HOCHI_URLS.items():
            print(f"  {category}記事取得中...")
            category_articles = fetch_hochi_articles(url, exclude_urls=hochi_existing)
            hochi_articles.extend(category_articles)
        
        print(f"スポーツ報知取得記事数: {len(hochi_articles)}")
        
        if hochi_articles:
            print("スポーツ報知記事例:")
            for i, article in enumerate(hochi_articles[:3]):
                print(f"  {i+1}. {article.get('title', '')}")
                print(f"     URL: {article.get('url', '')}")
        
        # 4. 日刊スポーツ記事取得テスト（既存URL除外）
        print("\n4. 日刊スポーツ記事取得テスト（既存URL除外）")
        nikkan_articles = fetch_all_nikkan_sports_articles(exclude_urls=nikkan_existing)
        print(f"日刊スポーツ取得記事数: {len(nikkan_articles)}")
        
        if nikkan_articles:
            print("日刊スポーツ記事例:")
            for i, article in enumerate(nikkan_articles[:3]):
                print(f"  {i+1}. {article.get('title', '')}")
                print(f"     URL: {article.get('url', '')}")
        
        # 5. 重複チェックテスト
        print("\n5. 重複チェックテスト")
        all_urls = set()
        for article in sponichi_articles + hochi_articles + nikkan_articles:
            url = article.get('url', '')
            if url in all_urls:
                print(f"重複URL発見: {url}")
            all_urls.add(url)
        
        print(f"総取得記事数: {len(all_urls)}")
        print("重複チェック完了")
        
    except Exception as e:
        print(f"[エラー] テスト失敗: {e}")
        raise

if __name__ == "__main__":
    test_existing_urls_functionality() 