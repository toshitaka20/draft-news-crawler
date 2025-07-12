# type: ignore
"""
サンスポ専用スクレイパー
"""

import requests
import time
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from config import MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, AI_KEYWORDS
from utils import clean_text, format_date_with_time, contains_keywords

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
    # タイトルはh1.article-headlineから取得
    title_tag = soup.select_one('h1.article-headline')
    if title_tag:
        title = clean_text(title_tag.get_text())
        if title:
            print(f"[DEBUG] タイトル発見 (h1.article-headline): {title}")
    # フォールバック: タイトルが見つからない場合はページタイトルを使用
    if not title and soup.title:
        title = clean_text(soup.title.get_text())
        print(f"[DEBUG] ページタイトルを使用: {title}")
    
    date = ''
    # 日付は記事ヘッダーから取得
    date_selectors = [
        '.article-date',
        '.publish-date',
        '.date',
        'time',
        '.article-header time'
    ]
    
    for selector in date_selectors:
        date_tag = soup.select_one(selector)
        if date_tag:
            date = format_date_with_time(clean_text(date_tag.get_text()))
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