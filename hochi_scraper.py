# type: ignore

import requests
from bs4 import BeautifulSoup
import time

def fetch_hochi_article_links(list_url, max_articles=20):
    """
    ul.article-list配下のaタグのみを記事URL抽出対象とする
    """
    res = requests.get(list_url)
    soup = BeautifulSoup(res.text, 'html.parser')
    links = []
    count = 0
    ul = soup.find('ul', class_='article-list')
    if not ul:
        print('[DEBUG] ul.article-listが見つかりません')
        return links
    for a in ul.find_all('a', href=True):
        href = a['href']
        url = None
        if href.startswith('/articles/'):
            url = 'https://hochi.news' + href
        elif href.startswith('https://hochi.news/articles/'):
            url = href
        if url and url not in links:
            links.append(url)
            count += 1
        if count >= max_articles:
            break
    print(f"[DEBUG] 抽出した記事URL数: {len(links)}")
    return links

def fetch_hochi_article_body(article_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(article_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    print("[DEBUG] HTML冒頭:", soup.prettify()[:20000])  # 先頭2000文字だけ出力
    
    title = ''
    title_tag = soup.select_one('h1.c-articleTitle, h1.article-title, h1')
    if title_tag:
        title = title_tag.get_text(strip=True)
    
    date = ''
    date_tag = soup.select_one('time, span.c-articleDate, .article-date')
    if date_tag:
        date = date_tag.get_text(strip=True)
    
    # 本文のデバッグ: 複数のセレクターを試す
    body = ''
    print("[DEBUG] 本文抽出の試行:")
    
    # 試行1: div.article__content > p.article__text
    content_div = soup.find('div', class_='article__content')
    if content_div:
        print("[DEBUG] div.article__content 発見")
        paragraphs = content_div.find_all('p', class_='article__text')
        print(f"[DEBUG] p.article__text 要素数: {len(paragraphs)}")
        if paragraphs:
            body = '\n'.join([p.get_text(strip=True) for p in paragraphs])
            print(f"[DEBUG] 本文抽出成功 (p.article__text): {len(body)}文字")
    
    # 試行2: 他のセレクターも試す
    if not body:
        print("[DEBUG] 他のセレクターを試行中...")
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
                print(f"[DEBUG] {selector} で {len(elements)} 要素発見")
                body = '\n'.join([p.get_text(strip=True) for p in elements])
                if body.strip():
                    print(f"[DEBUG] 本文抽出成功 ({selector}): {len(body)}文字")
                    break
    
    # 試行3: 最後の手段として、すべてのpタグから長いテキストを探す
    if not body:
        print("[DEBUG] すべてのpタグから長いテキストを探索")
        all_p = soup.find_all('p')
        long_texts = []
        for p in all_p:
            text = p.get_text(strip=True)
            if len(text) > 50:  # 50文字以上のテキスト
                long_texts.append(text)
        if long_texts:
            body = '\n'.join(long_texts[:10])  # 最初の10個まで
            print(f"[DEBUG] 長いテキストから抽出: {len(body)}文字")
    
    return title, date, body

def fetch_hochi_articles(list_url, max_articles=20, sleep_sec=1):
    """
    記事一覧ページから記事情報（タイトル・URL・日付・本文）をまとめて取得
    """
    links = fetch_hochi_article_links(list_url, max_articles)
    articles = []
    for url in links:
        try:
            title, date, body = fetch_hochi_article_body(url)
            articles.append({
                'title': title,
                'url': url,
                'date': date,
                'body': body
            })
            time.sleep(sleep_sec)  # アクセスマナー
        except Exception as e:
            print(f"[記事取得エラー] {url}: {e}")
    return articles

if __name__ == "__main__":
    list_urls = [
        "https://hochi.news/hsb/",  # 高校野球
        "https://hochi.news/tag/%E3%82%A2%E3%83%9E%E9%87%8E%E7%90%83"  # アマ野球
    ]
    for list_url in list_urls:
        print(f"\n=== {list_url} ===")
        articles = fetch_hochi_articles(list_url, max_articles=1)
        for art in articles:
            print(f"\nタイトル: {art['title']}\nURL: {art['url']}\n日付: {art['date']}\n本文全文:\n{art['body']}\n") 