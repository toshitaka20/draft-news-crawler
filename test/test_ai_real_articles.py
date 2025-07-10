#!/usr/bin/env python3
"""
実際の記事でAI処理精度向上テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai.gemini import extract_scout_comments_with_gemini
import requests
from bs4 import BeautifulSoup
import re

def fetch_real_article():
    """
    実際の記事を取得してテスト
    """
    # スポニチのキーワード記事を取得
    url = "https://www.sponichi.co.jp/baseball/tokusyu/university/"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 記事リンクを取得
        article_links = soup.select('ul.border-top a')
        
        for link in article_links[:5]:  # 最初の5件をテスト
            article_url = str(link.get('href', ''))
            if not article_url.startswith('http'):
                article_url = 'https://www.sponichi.co.jp' + article_url
            
            print(f"\n記事URL: {article_url}")
            
            # 記事詳細を取得
            article_response = requests.get(article_url, headers=headers)
            article_soup = BeautifulSoup(article_response.content, 'html.parser')
            
            # タイトル取得
            title_elem = article_soup.select_one('h1.title')
            title = title_elem.get_text().strip() if title_elem else "タイトルなし"
            
            # 本文取得
            body_elem = article_soup.select_one('[data-component="article-body"]')
            body = ""
            if body_elem:
                paragraphs = body_elem.select('p')
                body = '\n'.join([p.get_text().strip() for p in paragraphs])
            
            # キーワードチェック
            keywords = ["ドラフト", "スカウト", "コメント", "視察", "熱視線"]
            has_keywords = any(keyword in title or keyword in body for keyword in keywords)
            
            if has_keywords:
                print(f"タイトル: {title}")
                print(f"キーワードあり: {has_keywords}")
                print(f"本文（最初の200文字）: {body[:200]}...")
                
                # AI処理実行
                result = extract_scout_comments_with_gemini(
                    body, title, "2025年7月9日", article_url
                )
                
                print("\nAI処理結果:")
                if result:
                    print(result)
                else:
                    print("コメントなし")
                
                print("-" * 80)
                break  # 1件だけテスト
        
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    fetch_real_article() 