#!/usr/bin/env python3
"""
サンスポの日付取得テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup

def test_sanspo_date():
    """
    サンスポの日付取得をテスト
    """
    print("=== サンスポ日付取得テスト ===")
    
    # テスト用記事URL（実際の記事）
    test_url = "https://www.sanspo.com/article/20250710-DQH3F3PU3RG63BDTQURZ2PHBMM/"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
        res = requests.get(test_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        print(f"テストURL: {test_url}")
        print(f"ページタイトル: {soup.title.string if soup.title else 'なし'}")
        
        # 日付取得のテスト
        date_selectors = [
            '.article-date',
            '.publish-date',
            '.date',
            'time',
            '.article-header time',
            '.article-meta time',
            '.publish-time',
            '.article-info time'
        ]
        
        date_found = False
        for selector in date_selectors:
            date_tag = soup.select_one(selector)
            if date_tag:
                date_text = date_tag.get_text().strip()
                print(f"日付発見 ({selector}): {date_text}")
                date_found = True
                break
        
        if not date_found:
            print("日付が見つかりませんでした")
            
            # HTMLの構造を確認
            print("\n=== HTML構造確認 ===")
            article_header = soup.find('header') or soup.find('div', class_='article-header')
            if article_header:
                print("記事ヘッダー発見")
                print(article_header.prettify()[:500])
            else:
                print("記事ヘッダーが見つかりません")
                
            # 時間関連の要素を探す
            time_elements = soup.find_all('time')
            print(f"\ntime要素数: {len(time_elements)}")
            for i, time_elem in enumerate(time_elements[:3]):
                print(f"time要素{i+1}: {time_elem}")
        
    except Exception as e:
        print(f"[エラー] テスト失敗: {e}")

if __name__ == "__main__":
    test_sanspo_date() 