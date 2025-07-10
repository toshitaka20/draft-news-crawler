#!/usr/bin/env python3
"""
スポニチ社会人野球ページの構造確認
"""

import requests
from bs4 import BeautifulSoup

def test_sponichi_shakaijin():
    """スポニチ社会人野球ページの構造を確認"""
    url = "https://www.sponichi.co.jp/baseball/tokusyu/shakaijin/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }
    
    try:
        print(f"アクセス先URL: {url}")
        res = requests.get(url, headers=headers)
        print(f"ステータスコード: {res.status_code}")
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # ページタイトル
        title = soup.title.string if soup.title else 'なし'
        print(f"ページタイトル: {title}")
        
        # メインの記事リストを探す
        article_list = soup.find('ul', class_='border-top', attrs={'data-component': 'basic-list'})
        print(f"ul.border-top発見: {'あり' if article_list else 'なし'}")
        
        if article_list:
            links = article_list.find_all('a', href=True)
            print(f"記事リンク数: {len(links)}")
            
            for i, link in enumerate(links[:5]):
                href = link.get('href')
                text = link.get_text(strip=True)
                print(f"リンク{i+1}: {href}")
                print(f"  テキスト: {text[:50]}...")
        else:
            print("ul.border-topが見つからないため、他のセレクターを試します")
            
            # 代替セレクターを試す
            selectors = [
                '.article-list a',
                '.news-list a',
                '.list-article a',
                'article a',
                '.content a',
                '.article-item a',
                '.news-item a',
                '.list-item a',
                '.article a',
                'a[href*="/baseball/"]'
            ]
            
            for selector in selectors:
                found_links = soup.select(selector)
                if found_links:
                    print(f"{selector}で{len(found_links)}個のリンクを発見")
                    for i, link in enumerate(found_links[:3]):
                        href = link.get('href')
                        text = link.get_text(strip=True)
                        print(f"  {selector}リンク{i+1}: {href}")
                        print(f"    テキスト: {text[:50]}...")
                    break
        
        # HTMLの構造を確認
        print("\n=== HTML構造確認 ===")
        main_content = soup.find('main') or soup.find('div', class_='content') or soup.find('div', class_='main')
        if main_content:
            print("メインコンテンツエリア発見")
            # 最初の数行のHTMLを表示
            print(main_content.prettify()[:1000])
        else:
            print("メインコンテンツエリアが見つかりません")
            
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    test_sponichi_shakaijin() 