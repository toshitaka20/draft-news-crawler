#!/usr/bin/env python3
"""
サンスポスクレイパーの直接テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup

def test_sanspo_direct():
    """
    サンスポの記事取得を直接テスト
    """
    print("=== サンスポ記事取得テスト（直接） ===")
    
    # テスト用URL
    test_url = "https://www.sanspo.com/sports/baseball/high/"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
        res = requests.get(test_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        print(f"ページタイトル: {soup.title.string if soup.title else 'なし'}")
        
        # h2.sc__headlineで絞り込み
        headline_divs = soup.select('h2.sc__headline')
        print(f"h2.sc__headline要素数: {len(headline_divs)}")
        
        # 記事URLを抽出
        article_urls = []
        for i, headline_div in enumerate(headline_divs[:5]):  # 最初の5件のみ
            link = headline_div.find('a')
            if link:
                href = str(link.get('href', ''))
                if href and href.startswith('/article/'):
                    href = 'https://www.sanspo.com' + href
                    article_urls.append(href)
                    print(f"記事URL {i+1}: {href}")
        
        print(f"\n抽出された記事URL数: {len(article_urls)}")
        
        # 最初の記事の本文をテスト
        if article_urls:
            test_article_url = article_urls[0]
            print(f"\n=== 記事本文テスト: {test_article_url} ===")
            
            res = requests.get(test_article_url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # タイトル取得
            title_tag = soup.select_one('h1')
            title = title_tag.get_text().strip() if title_tag else 'なし'
            print(f"タイトル: {title}")
            
            # 本文取得
            article_text_divs = soup.select('.article__text')
            print(f"article__text要素数: {len(article_text_divs)}")
            
            if article_text_divs:
                body_parts = []
                for div in article_text_divs:
                    text = div.get_text().strip()
                    if text:
                        body_parts.append(text)
                
                body = '\n'.join(body_parts)
                print(f"本文（最初の200文字）: {body[:200]}...")
            else:
                print("本文が見つかりませんでした")
        
    except Exception as e:
        print(f"[エラー] テスト失敗: {e}")

if __name__ == "__main__":
    test_sanspo_direct() 