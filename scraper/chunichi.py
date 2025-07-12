# type: ignore
"""
中日スポーツ専用スクレイパー
"""

import requests
import time
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from config import MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, AI_KEYWORDS
from utils import clean_text, format_date_with_time, contains_keywords

def fetch_chunichi_article_links(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE) -> List[str]:
    """
    中日スポーツの記事一覧ページから記事URLを抽出
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(list_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    links: List[str] = []
    count = 0
    print(f"[DEBUG] 中日スポーツページ取得: {list_url}")
    # <main class="main-container">内の<a>を取得
    main_container = soup.find('main', class_='main-container')
    if main_container:
        article_links = main_container.find_all('a', href=True)
        for link in article_links:
            href = str(link.get('href', ''))
            # /article/ などで始まる記事URLを抽出（仮）
            if href.startswith('/article/'):
                href = 'https://www.chunichi.co.jp' + href
                if href not in links:
                    links.append(href)
                    count += 1
                    print(f"[DEBUG] 記事URL発見: {href}")
                    if count >= max_articles:
                        break
    print(f"[DEBUG] 中日スポーツ抽出した記事URL数: {len(links)}")
    return links[:max_articles]


def fetch_chunichi_article_body(article_url: str) -> tuple:
    """
    中日スポーツの記事本文を取得
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(article_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    print(f"[DEBUG] 中日スポーツ記事取得: {article_url}")
    # タイトル取得 <h1 class="ttl">
    title = ''
    title_tag = soup.select_one('h1.ttl')
    if title_tag:
        title = clean_text(title_tag.get_text())
        print(f"[DEBUG] タイトル発見: {title}")
    # 日付取得 <p class="sub-ttl">
    date = ''
    date_tag = soup.select_one('p.sub-ttl')
    if date_tag:
        date = format_date_with_time(clean_text(date_tag.get_text()))
        print(f"[DEBUG] 日付発見: {date}")
    # 本文取得 <div class="block">（複数ある場合は結合）
    body = ''
    block_divs = soup.select('div.block')
    if block_divs:
        body_parts = [clean_text(div.get_text()) for div in block_divs if clean_text(div.get_text())]
        body = '\n'.join(body_parts)
        print(f"[DEBUG] 本文発見: {body[:100]}...")
    return title, date, body

def fetch_chunichi_articles(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE, sleep_sec: int = SLEEP_SECONDS, exclude_urls: set = None, category: str = '') -> List[Dict[str, Any]]:
    """
    中日スポーツの記事を取得
    """
    articles = []
    article_urls = fetch_chunichi_article_links(list_url, max_articles)
    if exclude_urls is None:
        exclude_urls = set()
    for url in article_urls:
        if url in exclude_urls:
            print(f"[DEBUG] スキップ（既存）: {url}")
            continue
        try:
            title, date, body = fetch_chunichi_article_body(url)
            if title and body:
                full_text = f"{title}\n\n{body}"
                has_keywords = contains_keywords(full_text, AI_KEYWORDS)
                articles.append({
                    'title': title,
                    'url': url,
                    'date': date,
                    'body': body,
                    'source': '中日スポーツ',
                    'category': category,
                    'has_keywords': has_keywords
                })
                if has_keywords:
                    print(f"[DEBUG] キーワード記事発見: {title}")
                else:
                    print(f"[DEBUG] キーワードなし: {title}")
            time.sleep(sleep_sec)
        except Exception as e:
            print(f"[エラー] 中日スポーツ記事取得失敗: {url} - {e}")
            continue
    return articles

def fetch_all_chunichi_articles(exclude_urls: set = None) -> List[Dict[str, Any]]:
    """
    中日スポーツの全カテゴリの記事を取得
    """
    all_articles = []
    if exclude_urls is None:
        exclude_urls = set()
    chunichi_urls = {
        "高校野球": "https://www.chunichi.co.jp/chuspo/baseball/highschool",
        "大学・社会人": "https://www.chunichi.co.jp/chuspo/baseball/amateurbaseball"
    }
    for category, url in chunichi_urls.items():
        print(f"\n=== 中日スポーツ {category} ===")
        try:
            articles = fetch_chunichi_articles(url, MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, exclude_urls, category)
            all_articles.extend(articles)
        except Exception as e:
            print(f"[エラー] 中日スポーツ {category}: {e}")
    return all_articles 