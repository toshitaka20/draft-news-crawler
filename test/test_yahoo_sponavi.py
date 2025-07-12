#!/usr/bin/env python3
"""
Yahoo!スポーツナビスクレイパーのテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.yahoo_sponavi import fetch_yahoo_sponavi_articles, fetch_all_yahoo_sponavi_articles
from utils import filter_yahoo_unique_articles, deduplicate_articles_advanced

def test_single_category():
    """
    単一カテゴリのテスト
    """
    print("=== Yahoo!スポーツナビ 単一カテゴリテスト ===")
    
    # 高校野球の記事を5件取得
    articles = fetch_yahoo_sponavi_articles("高校野球", max_articles=5)
    
    print(f"\n取得記事数: {len(articles)}件")
    
    for i, article in enumerate(articles, 1):
        print(f"\n[{i}] {article['title']}")
        print(f"URL: {article['url']}")
        print(f"日付: {article['date']}")
        print(f"ソース: {article['source']}")
        print(f"カテゴリ: {article['category']}")
        print(f"キーワード: {'あり' if article.get('has_keywords') else 'なし'}")
        if article.get('body'):
            print(f"本文: {article['body'][:100]}...")
        print("-" * 50)

def test_all_categories():
    """
    全カテゴリのテスト
    """
    print("\n=== Yahoo!スポーツナビ 全カテゴリテスト ===")
    
    # 全カテゴリの記事を取得
    articles = fetch_all_yahoo_sponavi_articles()
    
    print(f"\n総取得記事数: {len(articles)}件")
    
    # カテゴリ別集計
    categories = {}
    keyword_count = 0
    
    for article in articles:
        category = article.get('category', '不明')
        categories[category] = categories.get(category, 0) + 1
        
        if article.get('has_keywords'):
            keyword_count += 1
    
    print("\n=== カテゴリ別記事数 ===")
    for category, count in categories.items():
        print(f"{category}: {count}件")
    
    print(f"\nキーワード記事数: {keyword_count}件")
    
    return articles

def test_deduplication():
    """
    重複除去のテスト
    """
    print("\n=== 重複除去テスト ===")
    
    # テスト用の重複記事を作成
    test_articles = [
        {
            'title': '同じタイトル',
            'body': '同じ本文の内容です。',
            'url': 'https://example.com/1',
            'source': 'スポニチ'
        },
        {
            'title': '同じタイトル',
            'body': '同じ本文の内容です。',
            'url': 'https://example.com/2',
            'source': 'Yahoo!スポーツナビ'
        },
        {
            'title': '異なるタイトル',
            'body': '異なる本文の内容です。',
            'url': 'https://example.com/3',
            'source': 'Yahoo!スポーツナビ'
        }
    ]
    
    print(f"重複除去前: {len(test_articles)}件")
    
    # 高度な重複除去を実行
    unique_articles = deduplicate_articles_advanced(test_articles)
    
    print(f"重複除去後: {len(unique_articles)}件")
    
    for article in unique_articles:
        print(f"- {article['title']} ({article['source']})")

def test_yahoo_filter():
    """
    Yahoo独自記事フィルタのテスト
    """
    print("\n=== Yahoo独自記事フィルタテスト ===")
    
    # 実際のYahoo記事を少量取得
    yahoo_articles = fetch_yahoo_sponavi_articles("高校野球", max_articles=3)
    
    # テスト用の既存5社記事を追加
    existing_articles = [
        {
            'title': 'テスト記事1',
            'body': 'テスト記事の本文です。',
            'url': 'https://test.com/1',
            'source': 'スポニチ'
        },
        {
            'title': 'テスト記事2',
            'body': 'テスト記事の本文です。',
            'url': 'https://test.com/2',
            'source': 'スポーツ報知'
        }
    ]
    
    all_articles = yahoo_articles + existing_articles
    
    print(f"フィルタ前記事数: {len(all_articles)}件")
    print(f"- Yahoo記事: {len(yahoo_articles)}件")
    print(f"- 既存5社記事: {len(existing_articles)}件")
    
    # Yahoo独自記事フィルタを実行
    filtered_articles = filter_yahoo_unique_articles(all_articles)
    
    print(f"\nフィルタ後記事数: {len(filtered_articles)}件")
    
    # ソース別集計
    sources = {}
    for article in filtered_articles:
        source = article.get('source', '不明')
        sources[source] = sources.get(source, 0) + 1
    
    print("\n=== フィルタ後ソース別記事数 ===")
    for source, count in sources.items():
        print(f"{source}: {count}件")

def main():
    """
    メインテスト関数
    """
    try:
        # 1. 単一カテゴリテスト
        test_single_category()
        
        # 2. 全カテゴリテスト
        articles = test_all_categories()
        
        # 3. 重複除去テスト
        test_deduplication()
        
        # 4. Yahoo独自記事フィルタテスト
        test_yahoo_filter()
        
        print("\n=== 全テスト完了 ===")
        
    except Exception as e:
        print(f"[ERROR] テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 