"""
Google Sheets連携
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any
from config import SPREADSHEET_NAME, CREDENTIALS_FILE

def setup_google_sheets():
    """
    Google Sheets APIの初期設定
    """
    try:
        # 認証情報の設定
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(credentials)
        
        return client.open(SPREADSHEET_NAME)
        
    except Exception as e:
        print(f"[エラー] Google Sheets設定失敗: {e}")
        raise

def setup_scout_sheet():
    """
    スカウトコメント用シートの設定
    """
    try:
        spreadsheet = setup_google_sheets()
        
        # ScoutCommentsシートを取得または作成
        try:
            scout_sheet = spreadsheet.worksheet("ScoutComments")
        except:
            scout_sheet = spreadsheet.add_worksheet(title="ScoutComments", rows=1000, cols=10)
        
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
        
        # メインシートを取得（Articlesシートを使用）
        worksheet = spreadsheet.worksheet("Articles")
        
        # ヘッダー行を準備
        headers = [
            '実行日時', '日付', 'ソース', 'カテゴリ', 'タイトル', 'URL', 
            '本文', 'キーワードフラグ', 'スカウトコメント'
        ]
        
        # 実行日時を取得
        from datetime import datetime
        execution_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # データ行を準備
        rows = []
        all_scout_rows = []  # 全スカウトコメント行
        
        for article in articles:
            # キーワードフラグを設定
            has_keywords = article.get('has_keywords', False)
            keyword_flag = 'TRUE' if has_keywords else 'FALSE'
            
            row = [
                execution_time,
                article.get('date', ''),
                article.get('source', ''),
                article.get('category', ''),
                article.get('title', ''),
                article.get('url', ''),
                article.get('body', ''),
                keyword_flag,
                article.get('scout_comments', '')
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
        
        # 新しい記事のみを追加（重複チェック付き）
        existing_urls = set()
        if len(existing_values) > 1:  # ヘッダー以外の行がある場合
            for row in existing_values[1:]:  # ヘッダーを除く
                if len(row) > 4:  # URL列（5列目）が存在
                    existing_urls.add(row[4])  # URLを記録
        
        # 新しい記事のみをフィルタリング
        new_rows = []
        for row in rows:
            article_url = row[4] if len(row) > 4 else ''  # URL列
            if article_url and article_url not in existing_urls:
                new_rows.append(row)
        
        # 新しい記事のみを追加（バッチ処理で分割）
        if new_rows:
            BATCH_SIZE = 50  # 1回に追加する行数
            try:
                for i in range(0, len(new_rows), BATCH_SIZE):
                    batch = new_rows[i:i+BATCH_SIZE]
                    worksheet.append_rows(batch)
                    print(f"[DEBUG] バッチ {i//BATCH_SIZE + 1}: {len(batch)}件追加")
                    # バッチ間で少し待機（API負荷軽減）
                    import time
                    time.sleep(0.5)
                print(f"[DEBUG] 新しい記事を{len(new_rows)}件追加しました")
            except Exception as e:
                print(f"[警告] 記事追加中にエラーが発生しました: {e}")
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
            scout_sheet = setup_scout_sheet()
            if deduped_scout_rows:
                BATCH_SIZE = 50  # 1回に追加する行数
                try:
                    for i in range(0, len(deduped_scout_rows), BATCH_SIZE):
                        batch = deduped_scout_rows[i:i+BATCH_SIZE]
                        scout_sheet.append_rows(batch)
                        print(f"[DEBUG] スカウトコメント バッチ {i//BATCH_SIZE + 1}: {len(batch)}件追加")
                        # バッチ間で少し待機（API負荷軽減）
                        import time
                        time.sleep(0.5)
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
        spreadsheet = setup_google_sheets()
        sheet = spreadsheet.worksheet("Articles")
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


def get_existing_urls_by_source(source: str) -> set[str]:
    """特定媒体の既存記事URLのセットを取得（ヘッダー名でマッピング）"""
    try:
        spreadsheet = setup_google_sheets()
        sheet = spreadsheet.worksheet("Articles")
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
        # ソース名のマッピング
        source_mapping = {
            'スポニチ': ['スポニチ', 'sponichi'],
            'スポーツ報知': ['スポーツ報知', 'hochi', '報知'],
            '日刊スポーツ': ['日刊スポーツ', 'nikkan', 'nikkan sports'],
            'サンスポ': ['サンスポ', 'sanspo']
        }
        target_sources = source_mapping.get(source, [source])
        for row in values[1:]:
            if len(row) > max(source_idx, url_idx):
                row_source = row[source_idx].lower()
                row_url = row[url_idx]
                if any(target in row_source for target in target_sources) and row_url:
                    urls.add(row_url)
        print(f"[DEBUG] {source}の既存URL数: {len(urls)}")
        return urls
    except Exception as e:
        print(f"[既存URL取得エラー] {source}: {e}")
        return set() 