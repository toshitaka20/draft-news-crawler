"""
汎用ユーティリティ関数
"""

import re
from typing import List, Dict, Any
from datetime import datetime

import hashlib
from difflib import SequenceMatcher

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

def calculate_content_hash(title: str, body: str) -> str:
    """
    記事のタイトル+本文からハッシュ値を計算
    """
    # 正規化（空白や改行を統一）
    normalized_title = re.sub(r'\s+', ' ', title.strip())
    normalized_body = re.sub(r'\s+', ' ', body.strip())
    
    # 結合してハッシュ値を計算
    content = f"{normalized_title}\n{normalized_body}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def get_source_priority(source: str) -> int:
    """
    ソースの優先度を取得（数値が小さいほど優先度が高い）
    """
    try:
        # Noneや空文字列の場合はデフォルト値を返す
        if not source:
            return 5
        
        # 文字列でない場合はデフォルト値を返す
        if not isinstance(source, str):
            print(f"[DEBUG] get_source_priority: 非文字列値 detected: {source} (type: {type(source)})")
            return 5
        
        priority_map = {
            # オリジナルソース（既存5社）が最優先
            'スポニチ': 1,
            'スポーツ報知': 1,
            '日刊スポーツ': 1,
            'サンスポ': 1,
            '中日スポーツ': 1,
            
            # Yahoo!スポーツナビは優先度低め
            'Yahoo!スポーツナビ': 10,
            
            # その他は中間
            'その他': 5
        }
        
        result = priority_map.get(source, 5)
        return result
    except Exception as e:
        print(f"[記事更新エラー] get_source_priority エラー: {e}")
        print(f"  入力値: {source} (type: {type(source)})")
        return 5

def are_articles_similar(article1: Dict[str, Any], article2: Dict[str, Any], threshold: float = 0.8) -> bool:
    """
    2つの記事の類似度を判定
    """
    try:
        title1 = article1.get('title', '') or ''
        title2 = article2.get('title', '') or ''
        body1 = article1.get('body', '') or ''
        body2 = article2.get('body', '') or ''
        
        # タイトルの類似度
        title_similarity = SequenceMatcher(None, title1, title2).ratio()
        
        # 本文の類似度
        body_similarity = SequenceMatcher(None, body1, body2).ratio()
        
        # 総合判定（タイトルと本文の両方が高い類似度の場合）
        return title_similarity > threshold and body_similarity > threshold
    except Exception as e:
        print(f"[記事更新エラー] 類似度計算エラー: {e}")
        print(f"  article1: {article1.get('title', '')[:50]}...")
        print(f"  article2: {article2.get('title', '')[:50]}...")
        return False

def deduplicate_articles_advanced(articles: List[Dict[str, Any]], similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    高度な重複除去（URL、タイトル、本文ベース）
    """
    print(f"[DEBUG] 高度な重複除去開始: {len(articles)}件")
    
    # 1. URLベースの重複除去
    seen_urls = set()
    url_unique_articles = []
    
    for article in articles:
        url = article.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            url_unique_articles.append(article)
    
    print(f"[DEBUG] URLベース重複除去後: {len(url_unique_articles)}件")
    
    # 2. ハッシュベースの重複除去
    seen_hashes = {}
    hash_unique_articles = []
    
    for article in url_unique_articles:
        title = article.get('title', '')
        body = article.get('body', '')
        
        # 内容が十分にある記事のみハッシュ化
        if len(title) > 10 and len(body) > 50:
            content_hash = calculate_content_hash(title, body)
            
            if content_hash not in seen_hashes:
                seen_hashes[content_hash] = article
                hash_unique_articles.append(article)
            else:
                # 重複した場合、優先度の高いソースを選択
                existing_article = seen_hashes[content_hash]
                existing_source = existing_article.get('source', '') or ''
                current_source = article.get('source', '') or ''
                
                try:
                    print(f"[DEBUG] ハッシュ重複除去 - 比較開始:")
                    print(f"  existing_article source: {existing_article.get('source')} (type: {type(existing_article.get('source'))})")
                    print(f"  current_article source: {article.get('source')} (type: {type(article.get('source'))})")
                    
                    existing_priority = get_source_priority(existing_source)
                    current_priority = get_source_priority(current_source)
                    
                    print(f"[DEBUG] 優先度比較: {current_priority} < {existing_priority} = {current_priority < existing_priority}")
                    
                    if current_priority < existing_priority:
                        # 現在の記事の方が優先度が高い場合、置き換える
                        seen_hashes[content_hash] = article
                        # リストからも置き換える
                        for i, a in enumerate(hash_unique_articles):
                            if a is existing_article:
                                hash_unique_articles[i] = article
                                break
                    
                    print(f"[DEBUG] ハッシュ重複検出: {title[:50]}... (優先: {article.get('source', '')} vs {existing_article.get('source', '')})")
                except Exception as e:
                    print(f"[記事更新エラー] ハッシュ重複除去エラー: {e}")
                    print(f"  existing_source: {existing_source} (type: {type(existing_source)})")
                    print(f"  current_source: {current_source} (type: {type(current_source)})")
                    print(f"  existing_priority: {existing_priority if 'existing_priority' in locals() else 'undefined'}")
                    print(f"  current_priority: {current_priority if 'current_priority' in locals() else 'undefined'}")
        else:
            # 内容が少ない記事はそのまま追加
            hash_unique_articles.append(article)
    
    print(f"[DEBUG] ハッシュベース重複除去後: {len(hash_unique_articles)}件")
    
    # 3. 類似度ベースの重複除去
    final_articles = []
    
    for article in hash_unique_articles:
        is_duplicate = False
        
        # 既存の記事との類似度をチェック
        for existing_article in final_articles:
            if are_articles_similar(article, existing_article, similarity_threshold):
                # 重複の場合、優先度の高いソースを選択
                existing_source = existing_article.get('source', '') or ''
                current_source = article.get('source', '') or ''
                
                try:
                    print(f"[DEBUG] 類似度重複除去 - 比較開始:")
                    print(f"  existing_article source: {existing_article.get('source')} (type: {type(existing_article.get('source'))})")
                    print(f"  current_article source: {article.get('source')} (type: {type(article.get('source'))})")
                    
                    existing_priority = get_source_priority(existing_source)
                    current_priority = get_source_priority(current_source)
                    
                    print(f"[DEBUG] 優先度比較: {current_priority} < {existing_priority} = {current_priority < existing_priority}")
                    
                    if current_priority < existing_priority:
                        # 現在の記事の方が優先度が高い場合、置き換える
                        for i, a in enumerate(final_articles):
                            if a is existing_article:
                                final_articles[i] = article
                                break
                    
                    print(f"[DEBUG] 類似度重複検出: {article.get('title', '')[:50]}... (優先: {article.get('source', '')} vs {existing_article.get('source', '')})")
                    is_duplicate = True
                    break
                except Exception as e:
                    print(f"[記事更新エラー] 類似度重複除去エラー: {e}")
                    print(f"  existing_source: {existing_source} (type: {type(existing_source)})")
                    print(f"  current_source: {current_source} (type: {type(current_source)})")
                    print(f"  existing_priority: {existing_priority if 'existing_priority' in locals() else 'undefined'}")
                    print(f"  current_priority: {current_priority if 'current_priority' in locals() else 'undefined'}")
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            final_articles.append(article)
    
    print(f"[DEBUG] 最終重複除去後: {len(final_articles)}件")
    
    # 4. 重複除去結果の統計
    sources = {}
    for article in final_articles:
        source = article.get('source', '不明')
        sources[source] = sources.get(source, 0) + 1
    
    print("\n[DEBUG] 重複除去後のソース別記事数:")
    for source, count in sorted(sources.items()):
        print(f"  {source}: {count}件")
    
    return final_articles

def filter_yahoo_unique_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Yahoo!スポーツナビの記事から、既存5社にない独自記事のみを抽出
    """
    yahoo_articles = [a for a in articles if a.get('source') == 'Yahoo!スポーツナビ']
    other_articles = [a for a in articles if a.get('source') != 'Yahoo!スポーツナビ']
    
    print(f"[DEBUG] Yahoo記事数: {len(yahoo_articles)}, その他記事数: {len(other_articles)}")
    
    unique_yahoo_articles = []
    
    for yahoo_article in yahoo_articles:
        is_unique = True
        
        # 既存5社の記事と比較
        for other_article in other_articles:
            if are_articles_similar(yahoo_article, other_article, threshold=0.7):
                print(f"[DEBUG] Yahoo重複除外: {yahoo_article.get('title', '')[:50]}... (重複: {other_article.get('source', '')})")
                is_unique = False
                break
        
        if is_unique:
            unique_yahoo_articles.append(yahoo_article)
    
    print(f"[DEBUG] Yahoo独自記事数: {len(unique_yahoo_articles)}")
    
    # 既存5社の記事 + Yahoo独自記事を結合
    return other_articles + unique_yahoo_articles

def deduplicate_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    記事の重複除去（高度版をデフォルトで使用）
    """
    return deduplicate_articles_advanced(articles) 

def compare_with_existing_articles(articles: List[Dict[str, Any]], similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    既存記事との内容比較のみを行う
    （記事間の重複除去は既に完了している前提）
    """
    print(f"[DEBUG] 既存記事との内容比較開始: {len(articles)}件")
    
    # Google Sheetsから既存記事の内容を取得
    from sheets.google_sheets import get_existing_articles_content, update_existing_article
    
    try:
        existing_articles = get_existing_articles_content()
        print(f"[DEBUG] 既存記事数: {len(existing_articles)}件")
    except Exception as e:
        print(f"[DEBUG] 既存記事取得エラー: {e}")
        existing_articles = []
    
    # 既存記事との内容比較のみ
    final_articles = []
    updated_articles = []  # 更新された記事のリスト
    
    for article in articles:
        is_duplicate_of_existing = False
        
        # 既存記事と類似度をチェック
        for existing_article in existing_articles:
            try:
                if are_articles_similar(article, existing_article, similarity_threshold):
                    # 重複の場合、優先度の高いソースを選択
                    existing_source = existing_article.get('source', '') or ''
                    current_source = article.get('source', '') or ''
                    
                    try:
                        print(f"[DEBUG] 既存記事比較 - 比較開始:")
                        print(f"  existing_article source: {existing_article.get('source')} (type: {type(existing_article.get('source'))})")
                        print(f"  current_article source: {article.get('source')} (type: {type(article.get('source'))})")
                        
                        existing_priority = get_source_priority(existing_source)
                        current_priority = get_source_priority(current_source)
                        
                        print(f"[DEBUG] 優先度比較: {current_priority} < {existing_priority} = {current_priority < existing_priority}")
                        
                        if current_priority < existing_priority:
                            # 新しい記事の方が優先度が高い場合、既存記事を更新
                            existing_url = existing_article.get('url', '')
                            if existing_url:
                                success = update_existing_article(existing_url, article)
                                if success:
                                    updated_articles.append(article)
                                    print(f"[DEBUG] 既存記事を更新: {article.get('title', '')[:50]}... (新: {article.get('source', '')} > 既存: {existing_article.get('source', '')})")
                        else:
                            # 既存記事の方が優先度が高い場合、新しい記事を除外
                            print(f"[DEBUG] 既存記事を優先: {article.get('title', '')[:50]}... (既存: {existing_article.get('source', '')} > 新: {article.get('source', '')})")
                        
                        is_duplicate_of_existing = True
                        break
                    except Exception as e:
                        print(f"[記事更新エラー] 既存記事比較エラー: {e}")
                        print(f"  existing_source: {existing_source} (type: {type(existing_source)})")
                        print(f"  current_source: {current_source} (type: {type(current_source)})")
                        print(f"  existing_priority: {existing_priority if 'existing_priority' in locals() else 'undefined'}")
                        print(f"  current_priority: {current_priority if 'current_priority' in locals() else 'undefined'}")
                        is_duplicate_of_existing = True
                        break
            except Exception as e:
                print(f"[記事更新エラー] 類似度チェックエラー: {e}")
                print(f"  article: {article.get('title', '')[:50]}...")
                print(f"  existing_article: {existing_article.get('title', '')[:50]}...")
                continue
        
        if not is_duplicate_of_existing:
            final_articles.append(article)
    
    print(f"[DEBUG] 既存記事との内容比較後: {len(final_articles)}件（新規）+ {len(updated_articles)}件（更新）")
    
    # 内容比較結果の統計
    all_processed = final_articles + updated_articles
    sources = {}
    for article in all_processed:
        source = article.get('source', '不明')
        sources[source] = sources.get(source, 0) + 1
    
    print("\n[DEBUG] 既存記事との内容比較後のソース別記事数:")
    for source, count in sorted(sources.items()):
        print(f"  {source}: {count}件")
    
    return final_articles  # 新規記事のみを返す（更新された記事は別途処理済み）

def filter_existing_yahoo_urls(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    既存のYahoo!スポーツナビ記事とのURL重複チェック
    URLのみで重複チェックを行い、ハッシュや類似度ベースのチェックは行わない
    """
    print(f"[DEBUG] 既存Yahoo記事URL重複チェック開始: {len(articles)}件")
    
    # 既存のYahoo!スポーツナビ記事のURLを取得（軽量版を使用）
    from sheets.google_sheets import get_existing_urls_by_source, get_existing_urls_lightweight
    
    try:
        # 軽量版を優先使用
        existing_yahoo_urls = get_existing_urls_by_source('Yahoo!スポーツナビ')
        print(f"[DEBUG] 既存Yahoo記事URL数: {len(existing_yahoo_urls)}件")
    except Exception as e:
        print(f"[DEBUG] 既存Yahoo記事URL取得エラー: {e}")
        existing_yahoo_urls = set()
    
    # URL重複チェック
    unique_articles = []
    duplicate_count = 0
    
    for article in articles:
        article_url = article.get('url', '')
        if article_url and article_url not in existing_yahoo_urls:
            unique_articles.append(article)
        elif article_url:
            duplicate_count += 1
            print(f"[DEBUG] 既存Yahoo記事URL重複除外: {article.get('title', '')[:50]}...")
    
    print(f"[DEBUG] 既存Yahoo記事URL重複除外: {duplicate_count}件")
    print(f"[DEBUG] 既存Yahoo記事URL重複チェック後: {len(unique_articles)}件")
    
    return unique_articles

def filter_yahoo_against_existing(yahoo_articles: List[Dict[str, Any]], threshold: float = 0.7) -> List[Dict[str, Any]]:
    """
    Yahoo!スポーツナビの記事から、既存5社の記事と重複しない独自記事のみを抽出
    """
    print(f"[DEBUG] Yahoo独自記事フィルタリング開始: {len(yahoo_articles)}件")
    
    # 既存5社の記事を取得
    from sheets.google_sheets import get_existing_articles_by_source
    
    existing_original_articles = []
    original_sources = ['スポニチ', 'スポーツ報知', '日刊スポーツ', 'サンスポ', '中日スポーツ']
    
    try:
        for source in original_sources:
            source_articles = get_existing_articles_by_source(source)
            existing_original_articles.extend(source_articles)
        
        print(f"[DEBUG] 既存5社の記事数: {len(existing_original_articles)}件")
    except Exception as e:
        print(f"[DEBUG] 既存5社記事取得エラー: {e}")
        existing_original_articles = []
    
    # Yahoo記事と既存5社記事を比較
    unique_yahoo_articles = []
    
    for yahoo_article in yahoo_articles:
        is_unique = True
        
        # 既存5社の記事と比較
        for existing_article in existing_original_articles:
            if are_articles_similar(yahoo_article, existing_article, threshold):
                print(f"[DEBUG] Yahoo重複除外: {yahoo_article.get('title', '')[:50]}... (重複: {existing_article.get('source', '')})")
                is_unique = False
                break
        
        if is_unique:
            unique_yahoo_articles.append(yahoo_article)
    
    print(f"[DEBUG] Yahoo独自記事数: {len(unique_yahoo_articles)}件")
    return unique_yahoo_articles

def smart_deduplicate_articles(
    articles: List[Dict[str, Any]],
    include_existing_comparison: bool = True,
    check_existing_yahoo_urls: bool = False
) -> List[Dict[str, Any]]:
    """
    スマートな重複除去（既存記事との比較オプション付き）
    1. まず記事間の重複除去（URL、ハッシュ、類似度ベース）
    2. 既存Yahoo記事とのURL重複チェック（オプション）
    3. 既存記事との比較（オプション）
    """
    print(f"[DEBUG] スマート重複除去開始: {len(articles)}件")
    
    # 1. まず記事間の重複除去（URL、ハッシュ、類似度ベース）
    deduplicated_articles = deduplicate_articles_advanced(articles)
    print(f"[DEBUG] 記事間重複除去後: {len(deduplicated_articles)}件")
    
    # 2. 既存Yahoo記事とのURL重複チェック
    if check_existing_yahoo_urls:
        deduplicated_articles = filter_existing_yahoo_urls(deduplicated_articles)
        print(f"[DEBUG] 既存Yahoo記事URL重複除去後: {len(deduplicated_articles)}件")
    else:
        print("[DEBUG] 既存Yahoo記事URL重複チェックをスキップ")
    
    # 3. 既存記事との内容比較（オプション）
    if include_existing_comparison:
        print("[DEBUG] 既存記事との内容比較を実行")
        return compare_with_existing_articles(deduplicated_articles)
    else:
        print("[DEBUG] 既存記事との内容比較をスキップ")
        return deduplicated_articles 
