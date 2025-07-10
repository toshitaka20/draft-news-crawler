#!/usr/bin/env python3
"""
サンスポスクレイパーのテスト
"""

from scraper.sanspo import fetch_all_sanspo_articles

def test_sanspo():
    """
    サンスポの記事取得をテスト
    """
    print("=== サンスポ記事取得テスト ===")
    
    try:
        # 全カテゴリの記事を取得（最大5件ずつ）
        articles = fetch_all_sanspo_articles()
        
        print(f"\n取得結果: {len(articles)}件")
        
        for i, article in enumerate(articles, 1):
            print(f"\n--- 記事 {i} ---")
            print(f"タイトル: {article.get('title', '')}")
            print(f"URL: {article.get('url', '')}")
            print(f"日付: {article.get('date', '')}")
            print(f"ソース: {article.get('source', '')}")
            print(f"カテゴリ: {article.get('category', '')}")
            print(f"本文: {article.get('body', '')[:100]}...")
            print(f"キーワードあり: {article.get('has_keywords', False)}")
            
    except Exception as e:
        print(f"[エラー] テスト失敗: {e}")

if __name__ == "__main__":
    test_sanspo() 