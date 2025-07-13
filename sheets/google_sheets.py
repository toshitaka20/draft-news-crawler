# type: ignore
"""
Google Sheets連携
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any
import time
import random
from config import SPREADSHEET_NAME, CREDENTIALS_FILE

# グローバルキャッシュ
_spreadsheet_cache = None
_worksheet_cache = {}

def setup_google_sheets(max_retries=3, base_delay=2):
    """
    Google Sheets APIの初期設定（リトライ機能付き、キャッシュ付き）
    """
    global _spreadsheet_cache
    
    # キャッシュがあれば返す
    if _spreadsheet_cache is not None:
        return _spreadsheet_cache
    
    for attempt in range(max_retries):
        try:
            # 認証情報の設定
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
            client = gspread.authorize(credentials)
            
            spreadsheet = client.open(SPREADSHEET_NAME)
            _spreadsheet_cache = spreadsheet  # キャッシュに保存
            return spreadsheet
            
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429:  # Rate limit exceeded
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"[警告] Google Sheets API レート制限 (429)。{delay:.1f}秒後にリトライ... (試行 {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[エラー] Google Sheets API レート制限。最大試行回数に達しました: {e}")
                    raise
            else:
                print(f"[エラー] Google Sheets設定失敗: {e}")
                raise
        except Exception as e:
            print(f"[エラー] Google Sheets設定失敗: {e}")
            raise

def get_worksheet(worksheet_name: str):
    """
    ワークシートを取得（キャッシュ付き）
    """
    global _worksheet_cache
    
    if worksheet_name not in _worksheet_cache:
        spreadsheet = setup_google_sheets()
        _worksheet_cache[worksheet_name] = spreadsheet.worksheet(worksheet_name)
    
    return _worksheet_cache[worksheet_name]

def clear_cache():
    """
    キャッシュをクリア（テスト用）
    """
    global _spreadsheet_cache, _worksheet_cache
    _spreadsheet_cache = None
    _worksheet_cache.clear()

def setup_scout_sheet():
    """
    スカウトコメント用シートの設定
    """
    try:
        spreadsheet = setup_google_sheets()
        
        # ScoutCommentsシートを取得または作成
        try:
            scout_sheet = get_worksheet("ScoutComments")
        except:
            scout_sheet = spreadsheet.add_worksheet(title="ScoutComments", rows=1000, cols=10)
            # キャッシュに追加
            _worksheet_cache["ScoutComments"] = scout_sheet
        
        # ヘッダー行を設定
        headers = [
            '選手名', '選手所属チーム', 'スカウト名', 'スカウト球団名', 
            'コメント内容', 'published_at', '記事URL'
        ]
        
        # ヘッダーがなければ追加
        if scout_sheet.row_count == 0:
            scout_sheet.append_row(headers)
        
        return scout_sheet
        
    except Exception as e:
        print(f"[エラー] スカウトシート設定失敗: {e}")
        raise

def update_sheets(articles: List[Dict[str, Any]]):
    """
    記事データをGoogle Sheetsに更新（メインシートとスカウトシート）
    """
    try:
        spreadsheet = setup_google_sheets()
        worksheet = get_worksheet("Articles")
        # デバッグ用: 書き込み先スプレッドシートとシート名を出力
        print(f"[DEBUG] 書き込み先スプレッドシート: {spreadsheet.url}, シート名: {worksheet.title}")
        
        # ヘッダー行を準備
        headers = [
            '実行日時', '日付', 'ソース', 'カテゴリ', 'URL', 'タイトル', 
            '本文', 'キーワードフラグ', 'スカウトコメント'
        ]
        
        # 実行日時をJSTで取得
        from datetime import datetime, timedelta, timezone
        JST = timezone(timedelta(hours=9), 'JST')
        execution_time = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
        
        # データ行を準備
        rows = []
        all_scout_rows = []  # 全スカウトコメント行
        
        for article in articles:
            # キーワードフラグを設定
            has_keywords = article.get('has_keywords', False)
            keyword_flag = 'TRUE' if has_keywords else 'FALSE'
            
            # データ順序: URL（5番目）、タイトル（6番目）
            row = [
                execution_time,                  # 実行日時
                article.get('date', ''),         # 日付
                article.get('source', ''),       # ソース
                article.get('category', ''),     # カテゴリ
                article.get('url', ''),          # URL（5番目）
                article.get('title', ''),        # タイトル（6番目）
                article.get('body', ''),         # 本文
                keyword_flag,                    # キーワードフラグ
                article.get('scout_comments', '')# スカウトコメント
            ]
            rows.append(row)
            
            # スカウトコメント行を収集
            scout_rows = article.get('scout_rows', [])
            all_scout_rows.extend(scout_rows)
        
        # 既存データを取得
        existing_values = worksheet.get_all_values()
        
        # ヘッダーが存在しない場合は追加
        if not existing_values:
            worksheet.append_row(headers)
        
        # 順番で重複チェック（URL列は5番目=インデックス4）
        existing_urls = set()
        if len(existing_values) > 1:  # ヘッダー以外の行がある場合
            for row in existing_values[1:]:  # ヘッダーを除く
                if len(row) > 4:  # URL列（5番目）が存在
                    existing_urls.add(row[4])  # URLを記録
        
        print(f"[DEBUG] 既存データ状況:")
        print(f"  - スプレッドシート総行数: {len(existing_values)}行（ヘッダー含む）")
        print(f"  - 既存記事数: {len(existing_values) - 1 if existing_values else 0}件")
        print(f"  - 既存URL数: {len(existing_urls)}件")
        
        # 新しい記事のみをフィルタリング（URL列は5番目=インデックス4）
        new_rows = []
        duplicate_count = 0
        for row in rows:
            article_url = row[4] if len(row) > 4 else ''  # URL列（5番目）
            if article_url and article_url not in existing_urls:
                new_rows.append(row)
            elif article_url:
                duplicate_count += 1
        
        # 重複チェック結果をログ出力
        print(f"[DEBUG] 重複チェック結果:")
        print(f"  - 処理対象記事数: {len(rows)}件")
        print(f"  - 既存URL重複除外: {duplicate_count}件")
        print(f"  - 新規追加対象: {len(new_rows)}件")
        
        # 新しい記事のみを追加（効率的な範囲指定）
        if new_rows:
            print(f"[DEBUG] 追加予定データ（new_rows）: {new_rows}")
            for r in new_rows:
                print(f"[DEBUG] 1行の長さ: {len(r)}, 内容: {r}")
            print(f"[DEBUG] ヘッダーの長さ: {len(headers)}, 内容: {headers}")
            
            def add_articles():
                # 現在の行数を取得
                current_row_count = len(existing_values)
                start_row = current_row_count + 1
                
                # A列からI列の範囲を指定して追加
                end_row = start_row + len(new_rows) - 1
                range_name = f"A{start_row}:I{end_row}"
                print(f"[DEBUG] 追加範囲: {range_name}")
                
                # 範囲を指定してデータを追加
                result = worksheet.update(range_name, new_rows)
                print(f"[DEBUG] API結果: {result}")
                print(f"[DEBUG] 新しい記事を{len(new_rows)}件追加しました")
                
                # 追加後の確認
                print("[DEBUG] 追加後の確認...")
                updated_values = worksheet.get_all_values()
                print(f"[DEBUG] 現在の総行数: {len(updated_values)}")
                if len(updated_values) > 0:
                    print(f"[DEBUG] 最後の行: {updated_values[-1]}")
            
            try:
                safe_sheet_operation(add_articles)
            except Exception as e:
                print(f"[警告] 記事追加中にエラーが発生しました: {e}")
                print(f"[DEBUG] エラーの詳細: {type(e).__name__}: {str(e)}")
                print("残りの記事は次回実行時に追加されます")
        else:
            print("[DEBUG] 新しい記事はありませんでした")
        
        # スカウトシートにコメントを追加
        if all_scout_rows:
            # --- deduplication start ---
            # 完全一致で重複除去、かつヘッダー行（カラム名）を除外
            seen = set()
            deduped_scout_rows = []
            header = ['選手名', '選手所属チーム', 'スカウト名', 'スカウト球団名', 'コメント内容', 'published_at', '記事URL']
            for row in all_scout_rows:
                row_tuple = tuple(row)
                if row_tuple not in seen and row != header:
                    seen.add(row_tuple)
                    # データ前処理：空白削除とコメントの「」削除
                    processed_row = []
                    for i, cell in enumerate(row):
                        if i == 4:  # コメント内容（5列目）
                            # 「」を削除
                            processed_cell = cell.replace('「', '').replace('」', '')
                        else:
                            # 先頭・末尾の空白を削除
                            processed_cell = cell.strip()
                        processed_row.append(processed_cell)
                    deduped_scout_rows.append(processed_row)
            # --- deduplication end ---
            
            def add_scout_comments():
                scout_sheet = setup_scout_sheet()
                if deduped_scout_rows:
                    BATCH_SIZE = 50  # 1回に追加する行数
                    for i in range(0, len(deduped_scout_rows), BATCH_SIZE):
                        batch = deduped_scout_rows[i:i+BATCH_SIZE]
                        scout_sheet.append_rows(batch)
                        print(f"[DEBUG] スカウトコメント バッチ {i//BATCH_SIZE + 1}: {len(batch)}件追加")
                        # バッチ間で少し待機（API負荷軽減）
                        time.sleep(0.5)
            
            try:
                safe_sheet_operation(add_scout_comments)
            except Exception as e:
                print(f"[警告] スカウトコメント追加中にエラーが発生しました: {e}")
                print("残りのスカウトコメントは次回実行時に追加されます")
        
        print(f"[DEBUG] Google Sheets更新完了: {len(articles)}件の記事, {len(all_scout_rows)}件のスカウトコメント")
        
    except FileNotFoundError:
        print("[警告] credentials.jsonが見つかりません。Google Sheets更新をスキップします。")
        print("記事データをコンソールに出力します:")
        for i, article in enumerate(articles, 1):
            print(f"\n--- 記事 {i} ---")
            print(f"タイトル: {article.get('title', '')}")
            print(f"URL: {article.get('url', '')}")
            print(f"日付: {article.get('date', '')}")
            print(f"ソース: {article.get('source', '')}")
            print(f"カテゴリ: {article.get('category', '')}")
            print(f"本文: {article.get('body', '')[:200]}...")
            print(f"スカウトコメント: {article.get('scout_comments', '')}")
    except Exception as e:
        print(f"[エラー] Google Sheets更新失敗: {e}")
        raise 

def get_existing_urls() -> set[str]:
    """Google Sheetsから既存記事URLのセットを取得（ヘッダー名でマッピング）"""
    try:
        sheet = get_worksheet("Articles")
        
        # 軽量な存在確認
        try:
            sheet.acell("A1").value
        except:
            print("[既存URL取得エラー] シートが存在しません")
            return set()
        
        urls = set()
        values = sheet.get_all_values()
        if not values or len(values) < 2:
            return set()
        header = values[0]
        header_map = {name: idx for idx, name in enumerate(header)}
        url_idx = header_map.get("URL")
        if url_idx is None:
            print("[既存URL取得エラー] 'URL'カラムが見つかりません")
            return set()
        for row in values[1:]:
            if len(row) > url_idx:
                urls.add(row[url_idx])
        return urls
    except Exception as e:
        print(f"[既存URL取得エラー] {e}")
        return set()

def check_sheet_exists(worksheet_name: str) -> bool:
    """
    シートの存在確認（軽量版）
    """
    try:
        sheet = get_worksheet(worksheet_name)
        sheet.acell("A1").value
        return True
    except:
        return False

def get_existing_urls_lightweight() -> set[str]:
    """
    軽量版の既存URL取得（最小限のAPI呼び出し）
    """
    try:
        if not check_sheet_exists("Articles"):
            return set()
        
        sheet = get_worksheet("Articles")
        
        # ヘッダー行のみ取得してURL列の位置を確認
        header_values = sheet.row_values(1)
        if not header_values:
            return set()
        
        url_idx = None
        for i, header in enumerate(header_values):
            if header == "URL":
                url_idx = i
                break
        
        if url_idx is None:
            print("[既存URL取得エラー] 'URL'カラムが見つかりません")
            return set()
        
        # URL列のみを取得（全行取得より軽量）
        urls = set()
        all_urls = sheet.col_values(url_idx + 1)  # gspreadは1ベース
        
        # ヘッダーを除いてURLを収集
        for url in all_urls[1:]:
            if url:  # 空でないURLのみ
                urls.add(url)
        
        return urls
        
    except Exception as e:
        print(f"[既存URL取得エラー] {e}")
        return set()

def safe_sheet_operation(operation, max_retries=3, base_delay=2):
    """
    シート操作のリトライ機能付きラッパー
    """
    for attempt in range(max_retries):
        try:
            return operation()
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429:  # Rate limit exceeded
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"[警告] Google Sheets API レート制限 (429)。{delay:.1f}秒後にリトライ... (試行 {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[エラー] Google Sheets API レート制限。最大試行回数に達しました: {e}")
                    raise
            else:
                raise
        except Exception as e:
            raise


def get_existing_urls_by_source(source: str) -> set[str]:
    """特定媒体の既存記事URLのセットを取得（ヘッダー名でマッピング）"""
    try:
        def get_urls_operation():
            sheet = get_worksheet("Articles")
            urls = set()
            values = sheet.get_all_values()
            if not values or len(values) < 2:
                return set()
            header = values[0]
            header_map = {name: idx for idx, name in enumerate(header)}
            source_idx = header_map.get("ソース")
            url_idx = header_map.get("URL")
            if source_idx is None or url_idx is None:
                print("[既存URL取得エラー] 'ソース'または'URL'カラムが見つかりません")
                return set()
            # ソース名の完全一致で検索
            for row in values[1:]:
                if len(row) > max(source_idx, url_idx):
                    row_source = row[source_idx]
                    row_url = row[url_idx]
                    if row_source == source and row_url:
                        urls.add(row_url)
            print(f"[DEBUG] {source}の既存URL数: {len(urls)}")
            return urls
        
        return safe_sheet_operation(get_urls_operation)
    except Exception as e:
        print(f"[既存URL取得エラー] {source}: {e}")
        return set() 

def get_existing_articles_content() -> List[Dict[str, Any]]:
    """
    Google Sheetsから既存記事の内容（タイトル・本文・ソース・URL）を取得
    重複除去のための内容比較に使用
    """
    try:
        def get_articles_operation():
            sheet = get_worksheet("Articles")
            articles = []
            
            values = sheet.get_all_values()
            if not values or len(values) < 2:
                return []
            
            header = values[0]
            header_map = {name: idx for idx, name in enumerate(header)}
            
            # 必要なカラムのインデックスを取得
            title_idx = header_map.get("タイトル")
            body_idx = header_map.get("本文")
            source_idx = header_map.get("ソース")
            url_idx = header_map.get("URL")
            
            if None in [title_idx, body_idx, source_idx, url_idx]:
                print("[既存記事取得エラー] 必要なカラムが見つかりません")
                return []
            
            # 既存記事のデータを取得
            for row in values[1:]:
                if len(row) > max(title_idx, body_idx, source_idx, url_idx):
                    article = {
                        'title': row[title_idx] if title_idx < len(row) else '',
                        'body': row[body_idx] if body_idx < len(row) else '',
                        'source': row[source_idx] if source_idx < len(row) else '',
                        'url': row[url_idx] if url_idx < len(row) else ''
                    }
                    
                    # 内容が十分にある記事のみを対象とする
                    if len(article['title']) > 10 and len(article['body']) > 50:
                        articles.append(article)
            
        print(f"[DEBUG] 既存記事の内容取得: {len(articles)}件")
        return articles
        
        return safe_sheet_operation(get_articles_operation)
        
    except Exception as e:
        print(f"[既存記事取得エラー] {e}")
        return []

def get_existing_articles_by_source(source: str) -> List[Dict[str, Any]]:
    """
    特定ソースの既存記事の内容を取得
    """
    try:
        all_articles = get_existing_articles_content()
        
        # ソース名の完全一致で検索
        filtered_articles = []
        for article in all_articles:
            if article['source'] == source:
                filtered_articles.append(article)
        
        print(f"[DEBUG] {source}の既存記事数: {len(filtered_articles)}件")
        return filtered_articles
        
    except Exception as e:
        print(f"[既存記事取得エラー] {source}: {e}")
        return []

def update_existing_article(article_url: str, new_article: Dict[str, Any]):
    """
    既存記事を新しい記事の内容で更新（優先度の高いソース用）
    """
    try:
        print(f"[DEBUG] update_existing_article 開始: {article_url}")
        sheet = get_worksheet("Articles")
        
        values = sheet.get_all_values()
        if not values or len(values) < 2:
            print("[DEBUG] シートにデータがありません")
            return False
        
        header = values[0]
        header_map = {name: idx for idx, name in enumerate(header)}
        
        # 必要なカラムのインデックスを取得
        url_idx = header_map.get("URL")
        title_idx = header_map.get("タイトル")
        body_idx = header_map.get("本文")
        source_idx = header_map.get("ソース")
        date_idx = header_map.get("日付")
        
        print(f"[DEBUG] カラムインデックス: URL={url_idx}, タイトル={title_idx}, 本文={body_idx}, ソース={source_idx}, 日付={date_idx}")
        
        if None in [url_idx, title_idx, body_idx, source_idx]:
            print("[記事更新エラー] 必要なカラムが見つかりません")
            return False
        
        # 対象記事の行を見つける
        for row_idx, row in enumerate(values[1:], start=2):  # 2行目から開始
            try:
                if len(row) > url_idx and row[url_idx] == article_url:
                    # 記事を更新
                    update_data = {}
                    if title_idx is not None and title_idx < len(header):
                        update_data[f"{chr(65 + title_idx)}{row_idx}"] = new_article.get('title', '')
                    if body_idx is not None and body_idx < len(header):
                        update_data[f"{chr(65 + body_idx)}{row_idx}"] = new_article.get('body', '')
                    if source_idx is not None and source_idx < len(header):
                        update_data[f"{chr(65 + source_idx)}{row_idx}"] = new_article.get('source', '')
                    if date_idx is not None and date_idx < len(header):
                        update_data[f"{chr(65 + date_idx)}{row_idx}"] = new_article.get('date', '')
                    
                    print(f"[DEBUG] 更新データ: {update_data}")
                    
                    if update_data:
                        # 各セルを個別に更新
                        for range_name, value in update_data.items():
                            sheet.update(range_name, [[value]])
                        print(f"[DEBUG] 既存記事を更新: {new_article.get('title', '')[:50]}...")
                        return True
            except Exception as e:
                print(f"[記事更新エラー] 行処理エラー: {e}")
                print(f"  row_idx: {row_idx}, url_idx: {url_idx}, row_length: {len(row)}")
                continue
        
        print(f"[DEBUG] 対象記事が見つかりませんでした: {article_url}")
        return False
        
    except Exception as e:
        print(f"[記事更新エラー] {e}")
        return False 