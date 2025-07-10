"""
各スクレイパーのデバッグ用テスト
"""

import requests
from bs4 import BeautifulSoup
import feedparser
from config import SPONICHI_URLS, HOCHI_URL, NIKKAN_FEEDS

def debug_sponichi():
    """スポニチのデバッグ"""
    print("=== スポニチデバッグ ===")
    
    for category, url in SPONICHI_URLS.items():
        print(f"\n--- {category} ---")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # すべてのaタグを取得
        all_links = soup.find_all('a', href=True)  # type: ignore
        print(f"全リンク数: {len(all_links)}")
        
        # /kiji/を含むリンクを確認
        kiji_links = []
        for link in all_links:
            href = str(link.get('href', ''))  # type: ignore
            if '/kiji/' in href:
                kiji_links.append(href)
        
        print(f"/kiji/を含むリンク数: {len(kiji_links)}")
        for i, link in enumerate(kiji_links[:5]):
            print(f"  {i+1}: {link}")

def debug_hochi():
    """スポーツ報知のデバッグ"""
    print("\n=== スポーツ報知デバッグ ===")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(HOCHI_URL, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # すべてのaタグを取得
    all_links = soup.find_all('a', href=True)  # type: ignore
    print(f"全リンク数: {len(all_links)}")
    
    # /sports/baseball/を含むリンクを確認
    baseball_links = []
    for link in all_links:
        href = str(link.get('href', ''))  # type: ignore
        if '/sports/baseball/' in href:
            baseball_links.append(href)
    
    print(f"/sports/baseball/を含むリンク数: {len(baseball_links)}")
    for i, link in enumerate(baseball_links[:5]):
        print(f"  {i+1}: {link}")

def debug_nikkan_sports():
    """日刊スポーツRSSのデバッグ"""
    print("\n=== 日刊スポーツRSSデバッグ ===")
    
    for rss_url in NIKKAN_FEEDS:
        print(f"\nRSS URL: {rss_url}")
        try:
            feed = feedparser.parse(rss_url)
            print(f"フィードタイトル: {feed.feed.get('title', 'N/A')}")
            print(f"エントリ数: {len(feed.entries)}")
            
            if feed.entries:
                print("最初のエントリ:")
                entry = feed.entries[0]  # type: ignore
                print(f"  タイトル: {str(entry.get('title', 'N/A'))}")
                print(f"  リンク: {str(entry.get('link', 'N/A'))}")
                print(f"  日付: {str(entry.get('published', 'N/A'))}")
            else:
                print("エントリがありません")
                
        except Exception as e:
            print(f"エラー: {e}")

if __name__ == "__main__":
    debug_sponichi()
    debug_hochi()
    debug_nikkan_sports() 