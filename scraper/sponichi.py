"""
スポニチ専用スクレイパー
"""

import requests
import time
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from config import SPONICHI_URLS, MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, REQUEST_TIMEOUT, AI_KEYWORDS
from utils import clean_text, format_date_with_time, contains_keywords

def fetch_sponichi_article_links(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE) -> List[str]:
    """
    スポニチの記事一覧ページから記事URLを抽出
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(list_url, headers=headers, timeout=REQUEST_TIMEOUT)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, 'html.parser')
    links: List[str] = []
    count = 0
    
    print(f"[DEBUG] スポニチページ取得: {list_url}")
    
    # スポニチの記事リンクを探す（ul.border-top配下のaタグをピンポイントで取得）
    article_list = soup.find('ul', class_='border-top', attrs={'data-component': 'basic-list'})
    
    if article_list:
        found_links = article_list.find_all('a', href=True)  # type: ignore
        print(f"[DEBUG] ul.border-top a で {len(found_links)} 要素発見")
        
        for link in found_links:
            href = str(link.get('href', ''))  # type: ignore
            if href and '/kiji/' in href and not href.endswith('/'):
                # 相対パスを絶対パスに変換
                if href.startswith('/'):
                    href = 'https://www.sponichi.co.jp' + href
                elif not href.startswith('http'):
                    href = 'https://www.sponichi.co.jp/' + href
                
                if href not in links:
                    links.append(href)
                    count += 1
                    print(f"[DEBUG] 記事URL発見: {href}")
                    if count >= max_articles:
                        break
    else:
        print("[DEBUG] ul.border-top が見つかりません")
        # フォールバック: 従来の方法
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
            print(f"[DEBUG] {selector} で {len(found_links)} 要素発見")
            
            for link in found_links:
                href = str(link.get('href', ''))
                if href and '/kiji/' in href and not href.endswith('/'):
                    # 相対パスを絶対パスに変換
                    if href.startswith('/'):
                        href = 'https://www.sponichi.co.jp' + href
                    elif not href.startswith('http'):
                        href = 'https://www.sponichi.co.jp/' + href
                    
                    if href not in links:
                        links.append(href)
                        count += 1
                        print(f"[DEBUG] 記事URL発見: {href}")
                        if count >= max_articles:
                            break
            
            if count >= max_articles:
                break
    
    print(f"[DEBUG] スポニチ抽出した記事URL数: {len(links)}")
    return links[:max_articles]

def fetch_sponichi_article_body(article_url: str) -> tuple:
    """
    スポニチの記事本文を取得
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(article_url, headers=headers, timeout=REQUEST_TIMEOUT)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, 'html.parser')
    
    print(f"[DEBUG] スポニチ記事取得: {article_url}")
    
    title = ''
    # タイトルはh1タグから取得
    title_tag = soup.select_one('h1')
    if title_tag:
        title = clean_text(title_tag.get_text())
        print(f"[DEBUG] タイトル発見: {title}")
    
    date = ''
    # 日付は<header data-component="article-header">配下の<div class="row">内の<p data-component="date-format">から取得
    article_header = soup.find('header', attrs={'data-component': 'article-header'})  # type: ignore
    if article_header:
        row_div = article_header.find('div', class_='row')  # type: ignore
        if row_div:
            date_p = row_div.find('p', attrs={'data-component': 'date-format'})  # type: ignore
            if date_p:
                date = format_date_with_time(clean_text(date_p.get_text()))
                print(f"[DEBUG] 日付発見: {date}")
    
    # 本文はdata-component="article-body"の配下の<p>タグのみから取得
    body = ''
    article_body_div = soup.find('div', attrs={'data-component': 'article-body'})  # type: ignore
    if article_body_div:
        p_tags = article_body_div.find_all('p')  # type: ignore
        if p_tags:
            body_parts = [clean_text(p.get_text()) for p in p_tags]
            body = '\n'.join(body_parts)
            print(f"[DEBUG] 本文発見 (data-component=article-body): {body[:100]}...")
    
    return title, date, body

def fetch_sponichi_articles(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE, sleep_sec: int = SLEEP_SECONDS, exclude_urls: set = None, category: str = '') -> List[Dict[str, Any]]:  # type: ignore
    """
    スポニチの記事を取得（すべての記事）
    """
    articles = []
    article_urls = fetch_sponichi_article_links(list_url, max_articles)
    if exclude_urls is None:
        exclude_urls = set()
    
    for url in article_urls:
        if url in exclude_urls:
            print(f"[DEBUG] スキップ（既存）: {url}")
            continue
        try:
            title, date, body = fetch_sponichi_article_body(url)
            if title and body:  # タイトルと本文が取得できた場合のみ追加
                # キーワードチェック
                full_text = f"{title}\n\n{body}"
                has_keywords = contains_keywords(full_text, AI_KEYWORDS)
                
                articles.append({
                    'title': title,
                    'url': url,
                    'date': date,
                    'body': body,
                    'source': 'スポニチ',
                    'category': category,
                    'has_keywords': has_keywords
                })
                
                if has_keywords:
                    print(f"[DEBUG] キーワード記事発見: {title}")
                else:
                    print(f"[DEBUG] キーワードなし: {title}")
            time.sleep(sleep_sec)
        except Exception as e:
            print(f"[エラー] スポニチ記事取得失敗: {url} - {e}")
            continue
    
    return articles

def fetch_all_sponichi_articles(exclude_urls: set = None) -> List[Dict[str, Any]]:  # type: ignore
    """
    スポニチの全カテゴリの記事を取得
    """
    all_articles = []
    if exclude_urls is None:
        exclude_urls = set()
    
    for category, url in SPONICHI_URLS.items():
        print(f"\n=== スポニチ {category} ===")
        try:
            articles = fetch_sponichi_articles(url, MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, exclude_urls, category)
            all_articles.extend(articles)
        except Exception as e:
            print(f"[エラー] スポニチ {category}: {e}")
    
    return all_articles 
