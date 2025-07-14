"""
Yahoo!スポーツナビ専用スクレイパー
高頻度更新対応、「もっと見る」機能対応
"""
# type: ignore
# mypy: disable-error-code=attr-defined,operator,return-value

import requests
import time
import json
import re
from typing import List, Dict, Any, Set, Optional
from bs4 import BeautifulSoup
from config import AI_KEYWORDS
from utils import clean_text, format_date_with_time, contains_keywords

class YahooSponaviScraper:
    def __init__(self):
        self.base_url = "https://sports.yahoo.co.jp"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def is_valid_yahoo_news_url(self, url: str) -> bool:
        """
        URLが有効なYahoo!ニュースのURLかどうかをチェック
        """
        if not url:
            return False
        
        # 正しいYahoo!ニュースのURLパターン
        yahoo_news_pattern = r'^https://news\.yahoo\.co\.jp/articles/[a-zA-Z0-9_-]+$'
        
        # パターンマッチング
        if re.match(yahoo_news_pattern, url):
            return True
        
        # 追加のチェック: /articles/ が含まれているか
        if '/articles/' not in url:
            return False
        
        # ドメインが正しいかチェック
        if not url.startswith('https://news.yahoo.co.jp/'):
            return False
        
        return True
    
    def get_category_url(self, category: str) -> str:
        """
        カテゴリに応じたURLを取得
        """
        category_urls = {
            "高校野球": "https://sports.yahoo.co.jp/list/news/?genre=hsb",
            "大学野球": "https://sports.yahoo.co.jp/list/news/?genre=baseball_univ"
        }
        
        return category_urls.get(category, category_urls["高校野球"])
    
    def fetch_article_list(self, category: str, max_articles: int = 50, exclude_urls: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """
        Yahoo!スポーツナビの記事一覧を取得
        """
        if exclude_urls is None:
            exclude_urls = set()
        
        url = self.get_category_url(category)
        
        try:
            print(f"[DEBUG] Yahoo!スポーツナビ {category} 記事一覧取得: {url}")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            
            # 記事リストを抽出（実際のHTMLセレクターに基づく）
            article_items = self._extract_article_items(soup)
            
            print(f"[DEBUG] Yahoo!スポーツナビ {category}: {len(article_items)}件の記事リンクを発見")
            
            for item in article_items:
                if len(articles) >= max_articles:
                    break
                
                article_info = self._parse_article_item(item, category)
                
                if article_info and article_info['url'] not in exclude_urls:
                    # URLフィルタリングを適用
                    if self.is_valid_yahoo_news_url(article_info['url']):
                        articles.append(article_info)
                        print(f"[DEBUG] 有効なYahoo!ニュースURL: {article_info['url']}")
                    else:
                        print(f"[DEBUG] 無効なURLを除外: {article_info['url']}")
            
            print(f"[DEBUG] Yahoo!スポーツナビ {category}: {len(articles)}件の有効な記事情報を取得")
            return articles
            
        except Exception as e:
            print(f"[ERROR] Yahoo!スポーツナビ {category} 記事一覧取得エラー: {e}")
            return []
    
    def _extract_article_items(self, soup: BeautifulSoup) -> List:
        """
        HTMLから記事アイテムを抽出
        """
        # Yahoo!スポーツナビの記事リストのセレクター候補（デバッグ結果に基づく）
        selectors = [
            # デバッグで発見した構造
            'ul.target_modules li',
            '.target_modules li',
            
            # 一般的なニュースリストのセレクター
            '.newsList li',
            '.newsItem',
            '.news-list li',
            '.article-list li',
            '.list-item',
            'li[data-module]',
            '.sc-list li',
            
            # より具体的なセレクター
            'ul li a[href*="/articles/"]',
            'div[data-module="NewsList"] li',
            '.articleList li'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                print(f"[DEBUG] セレクター '{selector}' で {len(items)} 件発見")
                return items
        
        # フォールバック: すべてのaタグからニュースURLを探す
        print("[DEBUG] フォールバック: 全aタグからニュースURLを検索")
        all_links = soup.find_all('a', href=True)
        news_items = []
        
        for link in all_links:
            href = link.get('href', '')  # type: ignore
            if href and '/articles/' in href:  # /news/ を削除、/articles/ のみに集中
                news_items.append(link)
        
        print(f"[DEBUG] フォールバック: {len(news_items)} 件のニュースリンクを発見")
        return news_items[:50]  # 最大50件に制限
    
    def _parse_article_item(self, item, category: str) -> Optional[Dict[str, Any]]:
        """
        記事アイテムから情報を抽出
        """
        try:
            # aタグを探す
            link = item.find('a') if hasattr(item, 'find') else item
            if not link:
                return None
            
            href = str(link.get('href', ''))
            if not href:
                return None
            
            # 絶対URLに変換（news.yahoo.co.jpドメインに対応）
            if href.startswith('/'):
                # Yahoo!ニュースのURLは news.yahoo.co.jp ドメイン
                href = 'https://news.yahoo.co.jp' + href
            elif not href.startswith('http'):
                return None
            
            # sports.yahoo.co.jp から news.yahoo.co.jp への変換は不要
            # 既に正しいドメインの場合はそのまま使用
            
            # タイトルを取得
            title = ''
            
            # タイトル取得候補
            title_candidates = [
                str(link.get_text()),
                str(link.get('title', '')),
                str(link.get('alt', ''))
            ]
            
            # 親要素からタイトルを探す
            if hasattr(item, 'find'):
                title_elements = item.find_all(['h3', 'h4', 'h5', '.title', '.headline'])
                for elem in title_elements:
                    title_candidates.append(str(elem.get_text()))
            
            for candidate in title_candidates:
                if candidate and len(candidate.strip()) > 5:
                    title = clean_text(candidate)
                    break
            
            if not title:
                return None
            
            # 配信元を取得
            source = 'Yahoo!スポーツナビ'
            
            # 日付情報を取得（可能であれば）
            date = ''
            if hasattr(item, 'find'):
                date_elements = item.find_all(['time', '.date', '.time'])
                for elem in date_elements:
                    date_text = elem.get('datetime') or elem.get_text()
                    if date_text:
                        date = format_date_with_time(clean_text(str(date_text)))
                        break
            
            return {
                'title': title,
                'url': href,
                'date': date,
                'source': source,
                'category': category,
                'body': '',  # 本文は後で取得
                'has_keywords': False  # 本文取得後に判定
            }
            
        except Exception as e:
            print(f"[ERROR] 記事アイテム解析エラー: {e}")
            return None
    
    def fetch_article_content(self, article_url: str) -> tuple:
        """
        記事の詳細内容を取得
        """
        try:
            print(f"[DEBUG] 記事詳細取得: {article_url}")
            
            response = self.session.get(article_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # タイトル取得
            title = self._extract_title(soup)
            
            # 日付取得
            date = self._extract_date(soup)
            
            # 本文取得
            body = self._extract_body(soup)
            
            return title, date, body
            
        except Exception as e:
            print(f"[ERROR] 記事詳細取得エラー {article_url}: {e}")
            return '', '', ''
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """記事タイトルを抽出（Yahoo!ニュース専用）"""
        
        # Yahoo!ニュースのタイトルはpage titleに含まれている
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text()
            # "（配信元） - Yahoo!ニュース"の部分を除去
            if ' - Yahoo!ニュース' in title_text:
                title_text = title_text.replace(' - Yahoo!ニュース', '')
            
            # 配信元の部分を除去（例: "（高校野球ドットコム）"）
            import re
            title_text = re.sub(r'（[^）]+）$', '', title_text)
            
            title = clean_text(title_text)
            if title:
                print(f"[DEBUG] タイトル取得: {title}")
                return title
        
        # フォールバック: 従来のセレクター
        title_selectors = [
            'h1.sc-bZQynM',
            'h1.articleTitle', 
            'h1.newsTitle',
            'h1[data-module="ArticleTitle"]',
            'h1',
            '.article-title h1',
            '.news-title h1'
        ]
        
        for selector in title_selectors:
            title_tag = soup.select_one(selector)
            if title_tag:
                title = clean_text(title_tag.get_text())
                if title and title != 'Yahoo!ニュース':
                    print(f"[DEBUG] h1タグからタイトル取得: {title}")
                    return title
        
        return ''
    
    def _extract_date(self, soup: BeautifulSoup) -> str:
        """記事日付を抽出（Yahoo!ニュース専用）"""
        
        # メタタグのpubdateから取得
        pubdate_meta = soup.find('meta', attrs={'name': 'pubdate'})
        if pubdate_meta:
            pubdate = pubdate_meta.get('content', '')
            if pubdate:
                formatted_date = format_date_with_time(clean_text(pubdate))
                print(f"[DEBUG] pubdateから日付取得: {formatted_date}")
                return formatted_date
        
        # 従来のセレクター
        date_selectors = [
            'time[datetime]',
            'time',
            '.article-date time',
            '.news-date time',
            '.date',
            '.sc-date',
            '[data-module="ArticleDate"]'
        ]
        
        for selector in date_selectors:
            date_tag = soup.select_one(selector)
            if date_tag:
                date_str = str(date_tag.get('datetime', '')) or str(date_tag.get_text())
                if date_str:
                    formatted_date = format_date_with_time(clean_text(date_str))
                    print(f"[DEBUG] {selector}から日付取得: {formatted_date}")
                    return formatted_date
        
        return ''
    
    def _extract_body(self, soup: BeautifulSoup) -> str:
        """記事本文を抽出（Yahoo!ニュース専用）"""
        
        # article_bodyクラスから本文を抽出（最優先）
        article_body_selectors = [
            '.article_body',  # デバッグで確認済み
            '.article-body',
            '.articleBody',
            '.sc-article-body',
            '.highres-article-body',
            '.newsBody',
            '.article-content',
            '.content',
            '[data-module="ArticleBody"]',
            '.news-text'
        ]
        
        for selector in article_body_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"[DEBUG] セレクター '{selector}' で {len(elements)} 件発見")
                body_parts = []
                for elem in elements:
                    # article_body内のテキストのみを抽出
                    text = self._extract_text_from_article_body(elem)
                    if text and len(text) > 10:  # 10文字以上の意味のある文章のみ
                        body_parts.append(text)
                        print(f"[DEBUG] 本文抽出成功: {len(text)}文字")
                
                if body_parts:
                    full_body = '\n'.join(body_parts)
                    if len(full_body) > 100:  # 100文字以上の場合は有効な本文とみなす
                        print(f"[DEBUG] セレクター '{selector}' から本文取得: {full_body[:100]}...")
                        return full_body
        
        # 従来の方法（フォールバック）
        body_selectors = [
            '.articleBody p',
            '.sc-article-body p',
            '.newsBody p', 
            '.article-content p',
            '.content p',
            '[data-module="ArticleBody"] p',
            '.news-text p'
        ]
        
        for selector in body_selectors:
            elements = soup.select(selector)
            if elements:
                body_parts = []
                for elem in elements:
                    text = clean_text(str(elem.get_text()))
                    if text and len(text) > 10:  # 10文字以上の意味のある文章のみ
                        body_parts.append(text)
                
                if body_parts:
                    full_body = '\n'.join(body_parts)
                    if len(full_body) > 100:  # 100文字以上の場合は有効な本文とみなす
                        print(f"[DEBUG] セレクター '{selector}' から本文取得: {full_body[:100]}...")
                        return full_body
        
        # 最終フォールバック: メタタグから取得
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = str(meta_desc.get('content', ''))
            if description and len(description) > 50:
                print(f"[DEBUG] メタタグから本文取得（フォールバック）: {description[:100]}...")
                return description
        
        return ''
    
    def _extract_text_from_article_body(self, article_body_elem) -> str:
        """article_body要素から本文テキストを抽出（Yahoo!ニュース専用）"""
        
        if not article_body_elem:
            return ''
        
        # 不要な要素を削除（コピーを作成）
        elem_copy = article_body_elem.__copy__()
        
        # 不要な要素を削除
        unwanted_selectors = [
            'a[href*="/articles/"]',  # 関連記事リンク
            '.related-articles',
            '.related-links', 
            '.recommend-articles',
            '.article-recommend',
            '.sc-recommend',
            '.yjSlinkDirectlinkHl',  # リンクハイライト
            'script',
            'style',
            'noscript',
            '.advertisement',
            '.ad',
            '.banner',
            '.social-share',
            '.share-buttons',
            '.article-footer',
            '.article-meta',
            '.article-info'
        ]
        
        for selector in unwanted_selectors:
            unwanted_elems = elem_copy.select(selector)
            for elem in unwanted_elems:
                elem.decompose()
        
        # テキストを抽出
        from utils import clean_text
        import re
        
        text = clean_text(str(elem_copy.get_text()))
        
        # 基本的な不要な文字列を除去（過度に厳しくしない）
        text = re.sub(r'\d+/\d+\([月火水木金土日]\)\s*\d+:\d+配信', '', text)
        text = re.sub(r'写真はイメージ', '', text)
        text = re.sub(r'Yahoo!ニュースのすべての機能を利用するためには.*?こちら', '', text, flags=re.DOTALL)
        text = re.sub(r'JavaScript.*?設定を変更', '', text, flags=re.DOTALL)
        
        # 複数の改行を単一の改行に統一
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # 前後の空白を除去
        text = text.strip()
        
        print(f"[DEBUG] _extract_text_from_article_body: {len(text)}文字抽出")
        
        return text

def fetch_yahoo_sponavi_articles(category: str, max_articles: int = 50, exclude_urls: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """
    Yahoo!スポーツナビの記事を取得（単一カテゴリ）
    """
    if exclude_urls is None:
        exclude_urls = set()
    
    scraper = YahooSponaviScraper()
    
    print(f"\n=== Yahoo!スポーツナビ {category} 記事取得開始 ===")
    
    # 記事一覧を取得
    articles = scraper.fetch_article_list(category, max_articles, exclude_urls)
    
    # 各記事の詳細を取得
    detailed_articles = []
    
    for i, article in enumerate(articles, 1):
        print(f"[{i}/{len(articles)}] 記事詳細取得中: {article['title'][:50]}...")
        
        # 記事本文が空の場合は詳細を取得
        if not article['body']:
            title, date, body = scraper.fetch_article_content(article['url'])
            
            if title:
                article['title'] = title
            if date:
                article['date'] = date
            if body:
                article['body'] = body
        
        # キーワードチェック
        if article['body']:
            full_text = f"{article['title']}\n\n{article['body']}"
            article['has_keywords'] = contains_keywords(full_text, AI_KEYWORDS)
            
            if article['has_keywords']:
                print(f"[DEBUG] キーワード記事発見: {article['title'][:50]}...")
        
        detailed_articles.append(article)
        
        # レート制限対策
        time.sleep(1.5)
    
    print(f"[INFO] Yahoo!スポーツナビ {category}: {len(detailed_articles)}件取得完了")
    return detailed_articles

def fetch_all_yahoo_sponavi_articles(exclude_urls: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """
    Yahoo!スポーツナビの全カテゴリ記事を取得
    """
    if exclude_urls is None:
        exclude_urls = set()
    
    all_articles = []
    categories = ["高校野球", "大学野球"]
    
    for category in categories:
        try:
            articles = fetch_yahoo_sponavi_articles(category, max_articles=30, exclude_urls=exclude_urls)
            all_articles.extend(articles)
            
            # カテゴリ間の待機時間
            time.sleep(2)
            
        except Exception as e:
            print(f"[ERROR] Yahoo!スポーツナビ {category} 取得エラー: {e}")
            continue
    
    print(f"\n=== Yahoo!スポーツナビ 全記事取得完了: {len(all_articles)}件 ===")
    
    # 結果サマリー
    keyword_count = sum(1 for a in all_articles if a.get('has_keywords', False))
    print(f"キーワード記事数: {keyword_count}件")
    
    return all_articles 