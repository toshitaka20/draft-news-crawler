"""
スポーツ報知専用スクレイパー
"""

import requests
import time
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from config import HOCHI_URLS, MAX_ARTICLES_PER_SOURCE, SLEEP_SECONDS, REQUEST_TIMEOUT
from utils import clean_text, format_date_with_time, annotate_article_signals

# 報知はUAだけのリクエストを弾くことがあるため、ブラウザ相当のヘッダをセッションで使い回す
HOCHI_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'Connection': 'keep-alive',
}

HOCHI_MAX_RETRIES = 3
# 連続アクセスで403になりやすいので、共通値より間隔を空ける
HOCHI_SLEEP_SECONDS = max(SLEEP_SECONDS, 2)
HOCHI_RETRY_WAIT_SECONDS = [5, 15, 30]

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HOCHI_HEADERS)
    return _session


def _reset_session() -> None:
    """403が続くときにセッション（Cookie等）を作り直す"""
    global _session
    if _session is not None:
        try:
            _session.close()
        except Exception:
            pass
    _session = None


def fetch_hochi_page(url: str, referer: Optional[str] = None) -> requests.Response:
    """
    スポーツ報知のページを取得（403/429/5xxはバックオフ付きでリトライ）
    """
    headers = {'Referer': referer, 'Sec-Fetch-Site': 'same-origin'} if referer else {}
    last_error: Optional[Exception] = None

    for attempt in range(HOCHI_MAX_RETRIES):
        try:
            res = _get_session().get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if res.status_code in (403, 429) or res.status_code >= 500:
                raise requests.exceptions.HTTPError(
                    f"{res.status_code} Client Error for url: {url}", response=res
                )
            res.raise_for_status()
            return res
        except requests.exceptions.RequestException as e:
            last_error = e
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            if attempt < HOCHI_MAX_RETRIES - 1:
                wait = HOCHI_RETRY_WAIT_SECONDS[min(attempt, len(HOCHI_RETRY_WAIT_SECONDS) - 1)]
                print(f"[DEBUG] スポーツ報知リトライ({attempt + 1}/{HOCHI_MAX_RETRIES - 1}) status={status} {wait}秒待機: {url}")
                if status in (403, 429):
                    _reset_session()
                time.sleep(wait)

    raise last_error if last_error else RuntimeError(f"スポーツ報知取得失敗: {url}")


def fetch_hochi_article_links(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE) -> List[str]:
    """
    スポーツ報知の記事一覧ページから記事URLを抽出
    ul.article-list配下のaタグのみを記事URL抽出対象とする
    """
    res = fetch_hochi_page(list_url)
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

def fetch_hochi_article_body(article_url: str, referer: Optional[str] = None) -> tuple:
    """
    スポーツ報知の記事本文を取得
    """
    res = fetch_hochi_page(article_url, referer=referer)
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

def fetch_hochi_articles(list_url: str, max_articles: int = MAX_ARTICLES_PER_SOURCE, sleep_sec: int = HOCHI_SLEEP_SECONDS, exclude_urls: set = None, category: str = '') -> List[Dict[str, Any]]:  # type: ignore
    """
    スポーツ報知の記事を取得（すべての記事）
    """
    articles = []
    try:
        article_urls = fetch_hochi_article_links(list_url, max_articles)
    except Exception as e:
        # 一覧が403等で取れても他カテゴリ・他媒体の処理は続行する
        print(f"[エラー] スポーツ報知一覧取得失敗: {list_url} - {e}")
        return articles
    if exclude_urls is None:
        exclude_urls = set()
    for url in article_urls:
        if url in exclude_urls:
            print(f"[DEBUG] スキップ（既存）: {url}")
            continue
        try:
            title, date, body = fetch_hochi_article_body(url, referer=list_url)
            if title and body:  # タイトルと本文が取得できた場合のみ追加
                article = {
                    'title': title,
                    'url': url,
                    'date': date,
                    'body': body,
                    'source': 'スポーツ報知',
                    'category': category
                }
                annotate_article_signals(article)
                articles.append(article)
                
                if article.get('has_keywords'):
                    print(f"[DEBUG] AI/注目度候補記事発見: {title}")
                else:
                    print(f"[DEBUG] 候補なし: {title}")
            time.sleep(sleep_sec)
        except Exception as e:
            print(f"[エラー] スポーツ報知記事取得失敗: {url} - {e}")
            continue
    return articles 
