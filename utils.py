"""
汎用ユーティリティ関数
"""

import re
from typing import List, Dict, Any
from datetime import datetime

def contains_keywords(text: str, keywords: List[str]) -> bool:
    """
    テキストにキーワードが含まれているかチェック
    """
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)

def clean_text(text: str) -> str:
    """
    テキストをクリーニング
    """
    if not text:
        return ""
    
    # 余分な空白を削除
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def format_date(date_str: str) -> str:
    """
    日付文字列をフォーマット（YYYY-MM-DD形式）
    """
    if not date_str:
        return ""
    
    try:
        # 様々な日付形式に対応
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%m/%d/%Y',
            '%d/%m/%Y'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # パースできない場合はそのまま返す
        return date_str
    except Exception:
        return date_str

def format_timestamp(date_str: str) -> str:
    """
    日付文字列をISO 8601形式（timestamp with time zone）にフォーマット
    """
    if not date_str:
        return ""
    
    try:
        # 様々な日付形式に対応
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%m/%d/%Y',
            '%d/%m/%Y'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # ISO 8601形式で出力（タイムゾーンはJSTとして扱う）
                return parsed_date.strftime('%Y-%m-%dT00:00:00+09:00')
            except ValueError:
                continue
        
        # パースできない場合はそのまま返す
        return date_str
    except Exception:
        return date_str

def deduplicate_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    記事の重複を除去（URLベース）
    """
    seen_urls = set()
    unique_articles = []
    
    for article in articles:
        url = article.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(article)
    
    return unique_articles 