#!/usr/bin/env python3
"""
サンスポのタイトル取得調査
"""

import requests
from bs4 import BeautifulSoup

def test_sanspo_title():
    """
    サンスポのタイトル取得を詳しく調査
    """
    print("=== サンスポタイトル取得調査 ===")
    
    # テスト用記事URL
    test_url = "https://www.sanspo.com/article/20250616-X6GPGDYBKNLLJOJTBRYGXQUQ5M/"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
        res = requests.get(test_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        print(f"テストURL: {test_url}")
        print(f"ページタイトル: {soup.title.string if soup.title else 'なし'}")
        
        # h1タグを探す
        h1_tags = soup.find_all('h1')
        print(f"h1タグ数: {len(h1_tags)}")
        for i, h1 in enumerate(h1_tags):
            print(f"h1タグ{i+1}: {h1}")
        
        # タイトル関連のセレクターを試す
        title_selectors = [
            'h1',
            '.article-title',
            '.title',
            '.headline',
            '.article-headline',
            'h1.article-title',
            'h1.title',
            'h1.headline'
        ]
        
        for selector in title_selectors:
            title_tag = soup.select_one(selector)
            if title_tag:
                title_text = title_tag.get_text().strip()
                print(f"タイトル発見 ({selector}): {title_text}")
            else:
                print(f"タイトルなし ({selector})")
        
        # HTMLの構造を確認
        print("\n=== HTML構造確認 ===")
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        if main_content:
            print("メインコンテンツ発見")
            # h1タグ周辺のHTMLを表示
            h1_nearby = main_content.find('h1')
            if h1_nearby:
                print("h1周辺のHTML:")
                print(h1_nearby.parent.prettify()[:500])
        
    except Exception as e:
        print(f"[エラー] テスト失敗: {e}")

if __name__ == "__main__":
    test_sanspo_title() 