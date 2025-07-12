"""
日刊スポーツ（RSS）専用スクレイパー
"""

import feedparser
import requests
import time
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from config import NIKKAN_FEEDS, MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, SCOUT_KEYWORDS, AI_KEYWORDS
from utils import clean_text, format_date_with_time, contains_keywords

def fetch_nikkan_article_body(url: str) -> str:
    """
    日刊スポーツの記事本文を取得（main.pyのfetch_body関数と同様）
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 日刊スポーツの記事本文セレクター
        body = soup.select_one('.article-body')
        if body:
            return clean_text(body.get_text())
        
        # フォールバック: 他のセレクターを試す
        selectors = [
            '.article-content',
            '.content',
            '.article__body',
            '.article__content',
            'article .text',
            '.main-content'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return clean_text(element.get_text())
        
        # 最後の手段: すべてのテキスト
        return clean_text(soup.get_text())
        
    except Exception as e:
        print(f"[エラー] 日刊スポーツ記事本文取得失敗: {url} - {e}")
        return ""

def fetch_nikkan_sports_articles(rss_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE, exclude_urls: set = None, category: str = '') -> List[Dict[str, Any]]:  # type: ignore
    """
    日刊スポーツのRSSフィードから記事を取得（すべての記事）
    """
    articles = []
    if exclude_urls is None:
        exclude_urls = set()
    
    print(f"[DEBUG] 日刊スポーツRSS取得: {rss_url}")
    
    try:
        feed = feedparser.parse(rss_url)
        print(f"[DEBUG] RSSエントリ数: {len(feed.entries)}")
        
        for entry in feed.entries[:max_articles]:
            try:
                title = clean_text(str(entry.get('title', '')))
                url = str(entry.get('link', ''))
                date = format_date_with_time(str(entry.get('published', '')))
                
                # 既存URLチェック
                if url in exclude_urls:
                    print(f"[DEBUG] スキップ（既存）: {url}")
                    continue
                
                # 記事本文を取得
                body = fetch_nikkan_article_body(url)
                
                # キーワードチェック（タイトルと本文で）
                full_text = f"{title}\n\n{body}"
                has_keywords = contains_keywords(full_text, AI_KEYWORDS)
                
                articles.append({
                    'title': title,
                    'url': url,
                    'date': date,
                    'body': body,
                    'source': '日刊スポーツ',
                    'category': category,
                    'has_keywords': has_keywords
                })
                
                if has_keywords:
                    print(f"[DEBUG] キーワード記事発見: {title}")
                else:
                    print(f"[DEBUG] キーワードなし: {title}")
                
                time.sleep(SLEEP_SECONDS)
                
            except Exception as e:
                print(f"[エラー] 日刊スポーツ記事処理失敗: {e}")
                continue
                
    except Exception as e:
        print(f"[エラー] 日刊スポーツRSS取得失敗: {e}")
    
    print(f"[DEBUG] 日刊スポーツ抽出した記事数: {len(articles)}")
    return articles

def fetch_all_nikkan_sports_articles(exclude_urls: set = None) -> List[Dict[str, Any]]:  # type: ignore
    """
    日刊スポーツの全RSSフィードから記事を取得
    """
    all_articles = []
    if exclude_urls is None:
        exclude_urls = set()
    
    for category, rss_url in NIKKAN_FEEDS.items():
        print(f"\n=== 日刊スポーツ RSS ({category}) ===")
        try:
            articles = fetch_nikkan_sports_articles(rss_url, MAX_ARTICLES_PER_SOURCE, exclude_urls, category)
            all_articles.extend(articles)
        except Exception as e:
            print(f"[エラー] 日刊スポーツ RSS ({category}): {e}")
    
    return all_articles 