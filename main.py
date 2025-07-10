# type: ignore
import os
import feedparser
import requests
from bs4 import BeautifulSoup, Tag
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
import json
import csv
import time
from typing import List, Dict, Optional, Any

# type: ignore を追加してlinterエラーを無効化
FEEDS = {
    "高校野球": "https://www.nikkansports.com/baseball/highschool/atom.xml",
    "大学・社会人野球": "https://www.nikkansports.com/baseball/amateur/atom.xml"
}

# スポーツ報知の記事一覧ページ
HOCHI_URLS = {
    "高校野球": "https://hochi.news/hsb/",
    "大学・社会人野球": "https://hochi.news/tag/%E3%82%A2%E3%83%9E%E9%87%8E%E7%90%83"
}

# スポニチの記事一覧ページ
SPONICHI_URLS = {
    "高校野球": "https://www.sponichi.co.jp/baseball/tokusyu/highschool/",
    "大学野球": "https://www.sponichi.co.jp/baseball/tokusyu/university/",
    "社会人野球": "https://www.sponichi.co.jp/baseball/tokusyu/shakaijin/"
}

KEYWORDS = ["ドラフト", "スカウト", "コメント", "視察"]

# credentials.sheets.jsonがなければ環境変数から生成
if not os.path.exists('credentials.json'):
    google_creds = os.environ.get('GOOGLE_CREDENTIALS')
    if google_creds:
        with open('credentials.sheets.json', 'w', encoding='utf-8') as f:
            f.write(google_creds)

# Google Sheets認証とシート準備
def setup_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.sheets.json', scope)  # type: ignore
    client = gspread.authorize(creds)  # type: ignore
    # 既存スプレッドシートのIDまたは新規作成
    try:
        sheet = client.open("DraftNews").sheet1
    except gspread.SpreadsheetNotFound:
        sheet = client.create("DraftNews").sheet1
    # ヘッダー行
    sheet.update([["カテゴリ", "タイトル", "公開日", "リンク", "本文", "フラグ"]])
    return sheet

def setup_scout_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.sheets.json', scope)  # type: ignore
    client = gspread.authorize(creds)  # type: ignore
    try:
        book = client.open("DraftNews")
        try:
            scout_sheet = book.worksheet("ScoutComments")
            # ヘッダーがなければ追加
            if scout_sheet.row_count == 0 or scout_sheet.row_values(1) != ['選手名', '選手所属チーム', 'スカウト名', 'スカウト球団名', 'コメント内容', '記事公開日', '記事URL']:
                scout_sheet.insert_row(['選手名', '選手所属チーム', 'スカウト名', 'スカウト球団名', 'コメント内容', '記事公開日', '記事URL'], 1)
        except gspread.WorksheetNotFound:
            scout_sheet = book.add_worksheet(title="ScoutComments", rows=100, cols=15)
            scout_sheet.update([['選手名', '選手所属チーム', 'スカウト名', 'スカウト球団名', 'コメント内容', '記事公開日', '記事URL']])
    except gspread.SpreadsheetNotFound:
        # DraftNews自体がなければ作成
        book = client.create("DraftNews")
        scout_sheet = book.add_worksheet(title="ScoutComments", rows=100, cols=15)
        scout_sheet.update([['選手名', '選手所属チーム', 'スカウト名', 'スカウト球団名', 'コメント内容', '記事公開日', '記事URL']])
    return scout_sheet

# Vertex AI用認証ファイルのセット（必要な箇所で呼び出し）
def set_vertexai_credentials():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.vertexai.json"

def fetch_body(url: str) -> str:
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        body = soup.select_one('.article-body')
        return body.get_text(strip=True) if body else ''
    except:
        return ''

# スポーツ報知の記事取得関数
def fetch_hochi_article_links(list_url: str, max_articles: int = 20) -> List[str]:
    """
    ul.article-list配下のaタグのみを記事URL抽出対象とする
    """
    res = requests.get(list_url)
    soup = BeautifulSoup(res.text, 'html.parser')
    links: List[str] = []
    count = 0
    ul = soup.find('ul', class_='article-list')
    if not ul:
        print('[DEBUG] ul.article-listが見つかりません')
        return links
    for a in ul.find_all('a', href=True):  # type: ignore
        href = a.get('href', '')  # type: ignore
        if not href:
            continue
        url: Optional[str] = None
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

def fetch_hochi_article_body(article_url: str) -> tuple:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(article_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
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
    
    # 試行1: div.article__content > p.article__text
    content_div = soup.find('div', class_='article__content')
    if content_div:
        paragraphs = content_div.find_all('p', class_='article__text')  # type: ignore
        if paragraphs:
            body = '\n'.join([p.get_text(strip=True) for p in paragraphs])
    
    # 試行2: 他のセレクターも試す
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
                body = '\n'.join([p.get_text(strip=True) for p in elements])
                if body.strip():
                    break
    
    # 試行3: 最後の手段として、すべてのpタグから長いテキストを探す
    if not body:
        all_p = soup.find_all('p')  # type: ignore
        long_texts = []
        for p in all_p:
            text = p.get_text(strip=True)
            if len(text) > 50:  # 50文字以上のテキスト
                long_texts.append(text)
        if long_texts:
            body = '\n'.join(long_texts[:10])  # 最初の10個まで
    
    return title, date, body

def fetch_hochi_articles(list_url: str, max_articles: int = 20, sleep_sec: int = 1) -> List[Dict[str, str]]:
    """
    記事一覧ページから記事情報（タイトル・URL・日付・本文）をまとめて取得
    """
    links = fetch_hochi_article_links(list_url, max_articles)
    articles: List[Dict[str, str]] = []
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

# スポニチの記事取得関数
def fetch_sponichi_article_links(list_url: str, max_articles: int = 20) -> List[str]:
    """
    スポニチの記事一覧ページから記事URLを抽出
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(list_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    links: List[str] = []
    count = 0
    
    print(f"[DEBUG] スポニチページ取得: {list_url}")
    print(f"[DEBUG] HTML冒頭: {res.text[:500]}")
    
    # スポニチの記事リンクを探す（より具体的なセレクターを試す）
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
        elements = soup.select(selector)
        print(f"[DEBUG] {selector} で {len(elements)} 要素発見")
        if elements:
            for a in elements:
                href = a.get('href', '')
                if not href:
                    continue
                
                # 相対URLを絶対URLに変換
                if href.startswith('/'):
                    url = 'https://www.sponichi.co.jp' + href
                elif href.startswith('http'):
                    url = href
                else:
                    continue
                
                # 記事URLのみを抽出（より緩い条件に変更）
                if ('/baseball/' in url and 
                    url not in links and
                    # カテゴリーページを除外
                    not url.endswith('/') and
                    # 画像やCSSファイルを除外
                    not any(ext in url for ext in ['.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.ico']) and
                    # 特集ページのトップを除外
                    not url.endswith('/tokusyu/') and
                    # 実際の記事ページかどうかをチェック
                    ('/baseball/' in url and len(url.split('/')) > 5)):
                    links.append(url)
                    count += 1
                    print(f"[DEBUG] 記事URL発見: {url}")
                    if count >= max_articles:
                        break
            if count >= max_articles:
                break
    
    print(f"[DEBUG] スポニチ抽出した記事URL数: {len(links)}")
    return links

def fetch_sponichi_article_body(article_url: str) -> tuple:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    res = requests.get(article_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    print(f"[DEBUG] スポニチ記事取得: {article_url}")
    
    title = ''
    # タイトルはh1タグから取得
    title_tag = soup.select_one('h1')
    if title_tag:
        title = title_tag.get_text(strip=True)
        print(f"[DEBUG] タイトル発見: {title}")
    
    date = ''
    # 日付は<header data-component="article-header">配下の<div class="row">内の<p data-component="date-format">から取得
    article_header = soup.find('header', attrs={'data-component': 'article-header'})
    if article_header:
        row_div = article_header.find('div', class_='row')
        if row_div:
            date_p = row_div.find('p', attrs={'data-component': 'date-format'})
            if date_p:
                date = date_p.get_text(strip=True)
                print(f"[DEBUG] 日付発見: {date}")
    
    # 本文はdata-component="article-body"の配下の<p>タグのみから取得
    body = ''
    article_body_div = soup.find('div', attrs={'data-component': 'article-body'})
    if article_body_div:
        p_tags = article_body_div.find_all('p')
        if p_tags:
            body = '\n'.join([p.get_text(strip=True) for p in p_tags])
            print(f"[DEBUG] 本文発見 (data-component=article-body): {body[:100]}...")
    
    return title, date, body

def fetch_sponichi_articles(list_url: str, max_articles: int = 20, sleep_sec: int = 1) -> List[Dict[str, str]]:
    """
    スポニチの記事一覧ページから記事情報（タイトル・URL・日付・本文）をまとめて取得
    """
    links = fetch_sponichi_article_links(list_url, max_articles)
    articles: List[Dict[str, str]] = []
    for url in links:
        try:
            title, date, body = fetch_sponichi_article_body(url)
            articles.append({
                'title': title,
                'url': url,
                'date': date,
                'body': body
            })
            time.sleep(sleep_sec)  # アクセスマナー
        except Exception as e:
            print(f"[スポニチ記事取得エラー] {url}: {e}")
    return articles

def extract_scout_comment_with_gemini_genai(article_text: str, title: str, published: str, link: str) -> Optional[str]:
    try:
        api_key = os.environ.get("GOOGLE_GENAI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_GENAI_API_KEYが設定されていません")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"""
あなたはプロ野球のスカウトコメント抽出AIです。
以下の記事本文から、プロ野球・MLB・侍ジャパン監督などの「球団スカウト・指導者」が特定の選手について述べた評価コメント・発言をすべて抽出してください。

【抽出対象の定義】
- 「スカウト」「監督」「コーチ」「関係者」などが、選手の能力・特徴・評価について述べた発言や、そう推測される記述
- 発言者名や球団名が明記されていない場合は「匿名スカウト」「不明」などで補完
- コメントが複数ある場合はすべて抽出し、1行ずつ出力
- 「」や『』やなどの引用符内の発言を優先的に抽出してください
- 「」や『』やなどの引用符内の発言は、原則として1つのスカウトコメントとして1行にまとめて出力してください。
- 選手名や球団名が文中で省略されている場合は、前後の文脈から推測して補完してください
- 抽出したコメントが選手評価でない場合は除外してください
- コメントがなければ何も出力しない

【出力カラム】
選手名, 選手所属チーム, スカウト名, スカウト球団名, コメント内容, 記事公開日, 記事URL

【出力形式】
- カンマ区切り（CSV形式、1行目はカラム名（ヘッダー））
- 2行目以降がデータ
- 1コメントにつき1行
- コメントがなければ何も出力しない

【記事情報】
タイトル: {title}
公開日: {published}
URL: {link}

【本文】
{article_text}
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"[Generative AI Geminiエラー] {e}")
        return None

def main():
    sheet = setup_sheet()
    scout_sheet = setup_scout_sheet()
    rows: List[List[str]] = []
    scout_rows: List[List[str]] = []

    # 既存記事URLのセットを作成
    existing_urls = set()
    try:
        existing_urls = set([row[3] for row in sheet.get_all_values()[1:]])  # 1行目はヘッダー
    except Exception as e:
        print(f"[既存URL取得エラー] {e}")

    # RSSフィードから記事取得
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            published = entry.get("published", "")
            content = fetch_body(link)

            # ここで重複チェック
            if link in existing_urls:
                print(f"スキップ（重複）: {link}")
                continue

            # フラグ判定
            flag = ''
            for kw in KEYWORDS:
                if kw in content:
                    flag = '⚑'
                    break
            print(f"\n📰 {category} / {title}")
            print(f"📅 {published}")
            print(f"🔗 {link}")
            print(f"📝 本文:\n{content[:300]}...")
            if flag:
                print(f"🚩 フラグ: {flag}")
                # スカウトコメント抽出（CSV形式で受け取る）
                scout_csv = extract_scout_comment_with_gemini_genai(content, title, published, link)
                print(f"[Gemini抽出結果] {scout_csv}")
                # CSVパースしてシート用データに
                try:
                    if scout_csv is None:
                        continue
                    reader = csv.reader(scout_csv.strip().splitlines())
                    rows_list = list(reader)
                    # 1行目はヘッダーなのでスキップ
                    for row in rows_list[1:]:
                        if len(row) == 7:
                            scout_rows.append(row)
                except Exception as e:
                    print(f"[スカウトコメントCSVパースエラー] {e}")
            # スプレッドシート用データ
            rows.append([category, title, published, link, content, flag])

    # スポーツ報知から記事取得
    for category, list_url in HOCHI_URLS.items():
        print(f"\n=== スポーツ報知 {category} ===")
        articles = fetch_hochi_articles(list_url, max_articles=5)
        for art in articles:
            title = art['title']
            link = art['url']
            published = art['date']
            content = art['body']

            # 重複チェック
            if link in existing_urls:
                print(f"スキップ（重複）: {link}")
                continue

            # フラグ判定
            flag = ''
            for kw in KEYWORDS:
                if kw in content:
                    flag = '⚑'
                    break
            print(f"\n📰 スポーツ報知 {category} / {title}")
            print(f"📅 {published}")
            print(f"🔗 {link}")
            print(f"📝 本文:\n{content[:300]}...")
            if flag:
                print(f"🚩 フラグ: {flag}")
                # スカウトコメント抽出
                scout_csv = extract_scout_comment_with_gemini_genai(content, title, published, link)
                print(f"[Gemini抽出結果] {scout_csv}")
                # CSVパースしてシート用データに
                try:
                    if scout_csv is None:
                        continue
                    reader = csv.reader(scout_csv.strip().splitlines())
                    rows_list = list(reader)
                    # 1行目はヘッダーなのでスキップ
                    for row in rows_list[1:]:
                        if len(row) == 7:
                            scout_rows.append(row)
                except Exception as e:
                    print(f"[スカウトコメントCSVパースエラー] {e}")
            # スプレッドシート用データ
            rows.append([f"スポーツ報知 {category}", title, published, link, content, flag])

    # スポニチから記事取得
    for category, list_url in SPONICHI_URLS.items():
        print(f"\n=== スポニチ {category} ===")
        articles = fetch_sponichi_articles(list_url, max_articles=5)
        for art in articles:
            title = art['title']
            link = art['url']
            published = art['date']
            content = art['body']

            # 重複チェック
            if link in existing_urls:
                print(f"スキップ（重複）: {link}")
                continue

            # フラグ判定
            flag = ''
            for kw in KEYWORDS:
                if kw in content:
                    flag = '⚑'
                    break
            print(f"\n📰 スポニチ {category} / {title}")
            print(f"📅 {published}")
            print(f"🔗 {link}")
            print(f"📝 本文:\n{content[:300]}...")
            if flag:
                print(f"🚩 フラグ: {flag}")
                # スカウトコメント抽出
                scout_csv = extract_scout_comment_with_gemini_genai(content, title, published, link)
                print(f"[Gemini抽出結果] {scout_csv}")
                # CSVパースしてシート用データに
                try:
                    if scout_csv is None:
                        continue
                    reader = csv.reader(scout_csv.strip().splitlines())
                    rows_list = list(reader)
                    # 1行目はヘッダーなのでスキップ
                    for row in rows_list[1:]:
                        if len(row) == 7:
                            scout_rows.append(row)
                except Exception as e:
                    print(f"[スカウトコメントCSVパースエラー] {e}")
            # スプレッドシート用データ
            rows.append([f"スポニチ {category}", title, published, link, content, flag])

    # スプレッドシートに一括書き込み
    if rows:
        sheet.append_rows(rows)
    if scout_rows:
        scout_sheet.append_rows(scout_rows)

if __name__ == "__main__":
    main()
