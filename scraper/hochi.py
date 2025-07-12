"""
スポーツ報知専用スクレイパー
"""

import requests
import time
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from config import HOCHI_URLS, MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, AI_KEYWORDS
from utils import clean_text, format_date_with_time, contains_keywords

def fetch_hochi_article_links(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE) -> List[str]:
    """
    スポーツ報知の記事一覧ページから記事URLを抽出
    ul.article-list配下のaタグのみを記事URL抽出対象とする
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(list_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    links: List[str] = []
    count = 0
    
    print(f"[DEBUG] スポーツ報知ページ取得: {list_url}")
    
    # ul.article-list配下のaタグをピンポイントで取得
    article_list = soup.find('ul', class_='article-list')
    
    if article_list:
        found_links = article_list.find_all('a', class_='article-list__unit', href=True)  # type: ignore
        print(f"[DEBUG] ul.article-list a.article-list__unit で {len(found_links)} 要素発見")
        
        for link in found_links:
            href = str(link.get('href', ''))  # type: ignore
            if not href:
                continue
            
            article_url: Optional[str] = None
            if href.startswith('/articles/'):
                article_url = 'https://hochi.news' + href
            elif href.startswith('https://hochi.news/articles/'):
                article_url = href
            
            if article_url and article_url not in links:
                links.append(article_url)
                count += 1
                print(f"[DEBUG] 記事URL発見: {article_url}")
                if count >= max_articles:
                    break
    else:
        print('[DEBUG] ul.article-list が見つかりません')
        # フォールバック: 従来の方法
        ul = soup.find('ul', class_='article-list')
        if ul:
            for a in ul.find_all('a', href=True):  # type: ignore
                href = str(a.get('href', ''))  # type: ignore
                if not href:
                    continue
                
                fallback_url: Optional[str] = None
                if href.startswith('/articles/'):
                    fallback_url = 'https://hochi.news' + href
                elif href.startswith('https://hochi.news/articles/'):
                    fallback_url = href
                
                if fallback_url and fallback_url not in links:
                    links.append(fallback_url)
                    count += 1
                    print(f"[DEBUG] 記事URL発見: {fallback_url}")
                    if count >= max_articles:
                        break
    
    print(f"[DEBUG] スポーツ報知抽出した記事URL数: {len(links)}")
    return links[:max_articles]

def fetch_hochi_article_body(article_url: str) -> tuple:
    """
    スポーツ報知の記事本文を取得
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(article_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    print(f"[DEBUG] スポーツ報知記事取得: {article_url}")
    
    title = ''
    title_tag = soup.select_one('h1.c-articleTitle, h1.article-title, h1')
    if title_tag:
        title = clean_text(title_tag.get_text())
        print(f"[DEBUG] タイトル発見: {title}")
    
    date = ''
    date_tag = soup.select_one('time, span.c-articleDate, .article-date')
    if date_tag:
        date = format_date_with_time(clean_text(date_tag.get_text()))
        print(f"[DEBUG] 日付発見: {date}")
    
    # 本文のデバッグ: 複数のセレクターを試す
    body = ''
    
    # 試行1: 直接 find_all('p', class_='preview__text') を試す
    article_paragraphs = soup.find_all('p', class_='preview__text')
    if article_paragraphs:
        print(f"[DEBUG] Found {len(article_paragraphs)} paragraphs with preview__text class")
        body = '\n'.join([clean_text(p.get_text()) for p in article_paragraphs])
        print(f"[DEBUG] 本文発見 (p.preview__text): {body[:100]}...")
    
    # 試行2: div.article__content > p[itemprop="articleBody"]
    if not body:
        content_div = soup.find('div', class_='article__content')
        print(f"[DEBUG] content_div: {'FOUND' if content_div else 'NOT FOUND'}")
        if content_div:
            paragraphs = content_div.find_all('p', attrs={'itemprop': 'articleBody'})  # type: ignore
            if paragraphs:
                body = '\n'.join([clean_text(p.get_text()) for p in paragraphs])
                print(f"[DEBUG] 本文発見 (div.article__content > p[itemprop=articleBody]): {body[:100]}...")
    
    # 試行3: 他のセレクターも試す
    if not body:
        # 一般的な記事本文セレクター
        selectors = [
            '.article-body p',
            '.article-content p',
            '.content p',
            '.text p',
            'article p',
            '.article__body p',
            '.article__text'
        ]
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                body = '\n'.join([clean_text(p.get_text()) for p in elements])
                if body.strip():
                    print(f"[DEBUG] 本文発見 ({selector}): {body[:100]}...")
                    break
    
    # 試行4: 最後の手段として、すべてのpタグから長いテキストを探す
    if not body:
        all_p = soup.find_all('p')  # type: ignore
        long_texts = []
        for p in all_p:
            text = clean_text(p.get_text())
            if len(text) > 50:  # 50文字以上のテキスト
                long_texts.append(text)
        if long_texts:
            body = '\n'.join(long_texts[:10])  # 最初の10個まで
            print(f"[DEBUG] 本文発見 (長いテキスト): {body[:100]}...")
    
    return title, date, body

def fetch_hochi_articles(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE, sleep_sec: int = SLEEP_SECONDS, exclude_urls: set = None, category: str = '') -> List[Dict[str, Any]]:  # type: ignore
    """
    スポーツ報知の記事を取得（すべての記事）
    """
    articles = []
    article_urls = fetch_hochi_article_links(list_url, max_articles)
    if exclude_urls is None:
        exclude_urls = set()
    for url in article_urls:
        if url in exclude_urls:
            print(f"[DEBUG] スキップ（既存）: {url}")
            continue
        try:
            title, date, body = fetch_hochi_article_body(url)
            if title and body:  # タイトルと本文が取得できた場合のみ追加
                # キーワードチェック
                full_text = f"{title}\n\n{body}"
                has_keywords = contains_keywords(full_text, AI_KEYWORDS)
                
                articles.append({
                    'title': title,
                    'url': url,
                    'date': date,
                    'body': body,
                    'source': 'スポーツ報知',
                    'category': category,
                    'has_keywords': has_keywords
                })
                
                if has_keywords:
                    print(f"[DEBUG] キーワード記事発見: {title}")
                else:
                    print(f"[DEBUG] キーワードなし: {title}")
            time.sleep(sleep_sec)
        except Exception as e:
            print(f"[エラー] スポーツ報知記事取得失敗: {url} - {e}")
            continue
    return articles 