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

def format_date_with_time(date_str: str) -> str:
    """
    日付文字列をフォーマット（時間情報付き形式）
    様々な日付形式に対応し、時間情報も含めて統一された形式で出力
    """
    if not date_str:
        return ""
    
    try:
        # 入力文字列をクリーニング
        date_str = date_str.strip()
        
        # 角括弧を除去（スポニチの形式: [ 2025年7月12日 06:00 ]）
        date_str = re.sub(r'^\[|\]$', '', date_str).strip()
        
        # 1. 既にISO 8601形式のタイムスタンプの場合
        iso_pattern = r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})[+-]\d{2}:\d{2}'
        match = re.match(iso_pattern, date_str)
        if match:
            year, month, day, hour, minute, second = match.groups()
            return f"{year}-{month}-{day} {hour}:{minute}"
        
        # 2. 日本語の日付パターン（時間情報付き）
        # 例: "2025年7月12日 06:00" → "2025-07-12 06:00"
        japanese_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s+(\d{1,2})[:時](\d{1,2})[分]?)?'
        match = re.match(japanese_pattern, date_str)
        if match:
            year, month, day, hour, minute = match.groups()
            if hour and minute:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute.zfill(2)}"
            else:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)} 00:00"
        
        # 3. 既にYYYY-MM-DD形式の場合
        if re.match(r'\d{4}-\d{2}-\d{2}$', date_str):
            return f"{date_str} 00:00"
        
        # 4. その他の日付形式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d %H:%M')
            except ValueError:
                continue
        
        # 5. 曜日名を含む場合の処理
        # 例: "2025年7月12日(金)" → "2025-07-12 00:00"
        weekday_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日\([月火水木金土日]\)'
        match = re.match(weekday_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)} 00:00"
        
        # 6. 英語月名を含む場合の処理
        # 例: "July 12, 2025" → "2025-07-12 00:00"
        try:
            from dateutil.parser import parse
            parsed_date = parse(date_str)
            return parsed_date.strftime('%Y-%m-%d %H:%M')
        except:
            pass
        
        # パースできない場合はそのまま返す
        return date_str
    except Exception:
        return date_str

def format_date(date_str: str) -> str:
    """
    日付文字列をフォーマット（YYYY-MM-DD形式）
    様々な日付形式に対応し、統一された形式で出力
    """
    if not date_str:
        return ""
    
    try:
        # 入力文字列をクリーニング
        date_str = date_str.strip()
        
        # 角括弧を除去（スポニチの形式: [ 2025年7月12日 06:00 ]）
        date_str = re.sub(r'^\[|\]$', '', date_str).strip()
        
        # 1. 既にISO 8601形式のタイムスタンプの場合
        iso_pattern = r'(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}'
        match = re.match(iso_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"
        
        # 2. 日本語の日付パターン（時間情報付き）
        # 例: "2025年7月12日 06:00" → "2025-07-12"
        japanese_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s+\d{1,2}[:時]\d{1,2}[分]?)?'
        match = re.match(japanese_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # 3. 既にYYYY-MM-DD形式の場合
        if re.match(r'\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        
        # 4. その他の日付形式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # 5. 曜日名を含む場合の処理
        # 例: "2025年7月12日(金)" → "2025-07-12"
        weekday_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日\([月火水木金土日]\)'
        match = re.match(weekday_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # 6. 英語月名を含む場合の処理
        # 例: "July 12, 2025" → "2025-07-12"
        try:
            from dateutil.parser import parse
            parsed_date = parse(date_str)
            return parsed_date.strftime('%Y-%m-%d')
        except:
            pass
        
        # パースできない場合はそのまま返す
        return date_str
    except Exception:
        return date_str

def format_timestamp(date_str: str) -> str:
    """
    日付文字列をISO 8601形式（timestamp with time zone）にフォーマット
    様々な日付形式に対応し、統一された形式で出力
    """
    if not date_str:
        return ""
    
    try:
        # 入力文字列をクリーニング
        date_str = date_str.strip()
        
        # 角括弧を除去（スポニチの形式: [ 2025年7月12日 06:00 ]）
        date_str = re.sub(r'^\[|\]$', '', date_str).strip()
        
        # 1. 既にISO 8601形式のタイムスタンプの場合
        iso_pattern = r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})[+-]\d{2}:\d{2}'
        match = re.match(iso_pattern, date_str)
        if match:
            year, month, day, hour, minute, second = match.groups()
            return f"{year}-{month}-{day}T{hour}:{minute}:{second}+09:00"
        
        # 2. 日本語の日付パターン（時間情報付き）
        # 例: "2025年7月12日 06:00" → "2025-07-12T06:00:00+09:00"
        japanese_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s+(\d{1,2})[:時](\d{1,2})[分]?)?'
        match = re.match(japanese_pattern, date_str)
        if match:
            year, month, day, hour, minute = match.groups()
            if hour and minute:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}T{hour.zfill(2)}:{minute.zfill(2)}:00+09:00"
            else:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}T00:00:00+09:00"
        
        # 3. 既にYYYY-MM-DD形式の場合
        if re.match(r'\d{4}-\d{2}-\d{2}$', date_str):
            return f"{date_str}T00:00:00+09:00"
        
        # 4. その他の日付形式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # ISO 8601形式で出力（タイムゾーンはJSTとして扱う）
                return parsed_date.strftime('%Y-%m-%dT%H:%M:%S+09:00')
            except ValueError:
                continue
        
        # 5. 曜日名を含む場合の処理
        weekday_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日\([月火水木金土日]\)'
        match = re.match(weekday_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}T00:00:00+09:00"
        
        # 6. 英語月名を含む場合の処理
        try:
            from dateutil.parser import parse
            parsed_date = parse(date_str)
            return parsed_date.strftime('%Y-%m-%dT%H:%M:%S+09:00')
        except:
            pass
        
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