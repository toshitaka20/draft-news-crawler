"""
スポーツ報知記事取得テスト（5件）
"""

from scraper.hochi import fetch_hochi_articles
from config import HOCHI_URLS

def test_hochi():
    """
    スポーツ報知の記事取得をテスト（5件）
    """
    print("=== スポーツ報知記事取得テスト（5件） ===")
    
    # 高校野球のみテスト
    test_url = HOCHI_URLS["高校野球"]
    print(f"\nテストURL: {test_url}")
    
    try:
        # 5件だけ取得
        articles = fetch_hochi_articles(test_url, max_articles=5, sleep_sec=0)
        
        print(f"\n取得結果: {len(articles)}件")
        
        for i, article in enumerate(articles, 1):
            print(f"\n--- 記事 {i} ---")
            print(f"タイトル: {article.get('title', '')}")
            print(f"URL: {article.get('url', '')}")
            print(f"日付: {article.get('date', '')}")
            print(f"本文: {article.get('body', '')[:100]}...")
            
    except Exception as e:
        print(f"[エラー] テスト失敗: {e}")

if __name__ == "__main__":
    test_hochi() 