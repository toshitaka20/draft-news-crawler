# type: ignore
"""
サンスポ記事収集・AIコメント抽出システム（テスト版）
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
import time
from config import MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, AI_KEYWORDS
from utils import clean_text, format_date, contains_keywords, deduplicate_articles
from ai.gemini import process_articles_with_ai
from sheets.google_sheets import update_sheets, get_existing_urls_by_source

def fetch_sanspo_article_links(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE) -> List[str]:
    """
    サンスポの記事一覧ページから記事URLを抽出
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(list_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    links: List[str] = []
    count = 0
    
    print(f"[DEBUG] サンスポページ取得: {list_url}")
    
    # サンスポの記事リンクを探す（h2.sc__headlineで絞ってからaタグを取得）
    headline_divs = soup.select('h2.sc__headline')
    print(f"[DEBUG] h2.sc__headline で {len(headline_divs)} 要素発見")
    
    for headline_div in headline_divs:
        link = headline_div.find('a')
        if link:
            href = str(link.get('href', ''))
            if href and href.startswith('/article/'):
                # 相対パスを絶対パスに変換
                href = 'https://www.sanspo.com' + href
                
                if href not in links:
                    links.append(href)
                    count += 1
                    print(f"[DEBUG] 記事URL発見: {href}")
                    if count >= max_articles:
                        break
    
    print(f"[DEBUG] サンスポ抽出した記事URL数: {len(links)}")
    return links[:max_articles]

def fetch_sanspo_article_body(article_url: str) -> tuple:
    """
    サンスポの記事本文を取得
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(article_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    print(f"[DEBUG] サンスポ記事取得: {article_url}")
    
    title = ''
    # タイトルはh1タグから取得
    title_tag = soup.select_one('h1')
    if title_tag:
        title = clean_text(title_tag.get_text())
        print(f"[DEBUG] タイトル発見: {title}")
    
    date = ''
    # 日付は記事ヘッダーから取得
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
    
    for selector in date_selectors:
        date_tag = soup.select_one(selector)
        if date_tag:
            date = format_date(clean_text(date_tag.get_text()))
            print(f"[DEBUG] 日付発見: {date}")
            break
    
    # 本文は記事本文エリアから取得（article__textクラスを使用）
    body = ''
    article_text_divs = soup.select('.article__text')
    
    if article_text_divs:
        body_parts = []
        for div in article_text_divs:
            text = clean_text(div.get_text())
            if text:
                body_parts.append(text)
        
        if body_parts:
            body = '\n'.join(body_parts)
            print(f"[DEBUG] 本文発見 (article__text): {body[:100]}...")
    
    return title, date, body

def fetch_sanspo_articles(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE, sleep_sec: int = SLEEP_SECONDS, exclude_urls: set = None, category: str = '') -> List[Dict[str, Any]]:
    """
    サンスポの記事を取得
    """
    articles = []
    article_urls = fetch_sanspo_article_links(list_url, max_articles)
    if exclude_urls is None:
        exclude_urls = set()
    
    for url in article_urls:
        if url in exclude_urls:
            print(f"[DEBUG] スキップ（既存）: {url}")
            continue
        try:
            title, date, body = fetch_sanspo_article_body(url)
            if title and body:  # タイトルと本文が取得できた場合のみ追加
                # キーワードチェック
                full_text = f"{title}\n\n{body}"
                has_keywords = contains_keywords(full_text, AI_KEYWORDS)
                
                articles.append({
                    'title': title,
                    'url': url,
                    'date': date,
                    'body': body,
                    'source': 'サンスポ',
                    'category': category,
                    'has_keywords': has_keywords
                })
                
                if has_keywords:
                    print(f"[DEBUG] キーワード記事発見: {title}")
                else:
                    print(f"[DEBUG] キーワードなし: {title}")
            time.sleep(sleep_sec)
        except Exception as e:
            print(f"[エラー] サンスポ記事取得失敗: {url} - {e}")
            continue
    
    return articles

def fetch_all_sanspo_articles(exclude_urls: set = None) -> List[Dict[str, Any]]:
    """
    サンスポの全カテゴリの記事を取得
    """
    all_articles = []
    if exclude_urls is None:
        exclude_urls = set()
    
    # サンスポのURL設定
    sanspo_urls = {
        "高校野球": "https://www.sanspo.com/sports/baseball/high/",
        "大学野球": "https://www.sanspo.com/sports/baseball/univ/",
        "社会人野球": "https://www.sanspo.com/sports/baseball/non-pro/"
    }
    
    for category, url in sanspo_urls.items():
        print(f"\n=== サンスポ {category} ===")
        try:
            articles = fetch_sanspo_articles(url, MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, exclude_urls, category)
            all_articles.extend(articles)
        except Exception as e:
            print(f"[エラー] サンスポ {category}: {e}")
    
    return all_articles

def main():
    """
    メイン処理（サンスポのみ）
    """
    print("=== サンスポ記事収集・AIコメント抽出システム（テスト版） ===")
    
    all_articles = []
    
    try:
        # 1. サンスポ記事取得
        print("\n1. サンスポ記事取得中...")
        sanspo_existing_urls = get_existing_urls_by_source('サンスポ')
        sanspo_articles = fetch_all_sanspo_articles(exclude_urls=sanspo_existing_urls)
        all_articles.extend(sanspo_articles)
        print(f"サンスポ記事数: {len(sanspo_articles)}")
        
        # 2. 重複除去
        print("\n2. 重複除去中...")
        unique_articles = deduplicate_articles(all_articles)
        print(f"重複除去後記事数: {len(unique_articles)}")
        
        # 3. AIコメント抽出（キーワードあり記事のみ）
        print("\n3. AIコメント抽出中...")
        keyword_articles = [a for a in unique_articles if a.get('has_keywords', False)]
        processed_keyword_articles = process_articles_with_ai(keyword_articles)
        print(f"AI処理完了記事数: {len(processed_keyword_articles)}")
        
        # 4. キーワードなし記事にもscout_comments/scout_rowsをセット
        no_keyword_articles = [a for a in unique_articles if not a.get('has_keywords', False)]
        for a in no_keyword_articles:
            a['scout_comments'] = "キーワードなし"
            a['scout_rows'] = []
        
        # 5. 全記事をマージしてGoogle Sheets更新
        all_processed = processed_keyword_articles + no_keyword_articles
        print("\n4. Google Sheets更新中...")
        update_sheets(all_processed)
        
        print(f"\n=== 処理完了 ===")
        print(f"総記事数: {len(all_processed)}")
        
        # 結果サマリー
        sources = {}
        for article in all_processed:
            source = article.get('source', '不明')
            sources[source] = sources.get(source, 0) + 1
        
        print("\n=== ソース別記事数 ===")
        for source, count in sources.items():
            print(f"{source}: {count}件")
        
        # カテゴリ別サマリー
        categories = {}
        for article in all_processed:
            category = article.get('category', '不明')
            categories[category] = categories.get(category, 0) + 1
        
        print("\n=== カテゴリ別記事数 ===")
        for category, count in categories.items():
            print(f"{category}: {count}件")
        
    except Exception as e:
        print(f"[エラー] メイン処理失敗: {e}")
        raise

if __name__ == "__main__":
    main() 