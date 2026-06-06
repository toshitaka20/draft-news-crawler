"""
既存5社専用記事収集・AIコメント抽出システム
1日3回実行（9時、15時、21時）
"""

from typing import List, Dict, Any
from scraper.sponichi import fetch_all_sponichi_articles
from scraper.hochi import fetch_hochi_articles
from scraper.nikkan_sports import fetch_all_nikkan_sports_articles
from scraper.sanspo import fetch_all_sanspo_articles
from scraper.chunichi import fetch_all_chunichi_articles
from ai.gemini import process_articles_with_ai
from sheets.google_sheets import update_sheets, get_existing_urls_by_source
from database.supabase_client import (
    get_existing_crawled_urls_by_source,
    insert_scout_comments_directly,
    upsert_crawled_articles,
)
from utils import smart_deduplicate_articles
from config import HOCHI_URLS

def get_existing_urls_for_source(source: str) -> set:
    """
    DBを優先して既存URLを取得する。移行期間中はSheetsをfallbackにする。
    """
    db_urls = get_existing_crawled_urls_by_source(source)
    if db_urls:
        return db_urls

    print(f"[DEBUG] DB既存URLが空のためSheets fallback: {source}")
    return get_existing_urls_by_source(source)

def main():
    """
    既存5社専用メイン処理
    """
    print("=== 既存5社記事収集・AIコメント抽出システム ===")
    
    all_articles = []
    
    try:
        # 1. スポニチ記事取得
        print("\n1. スポニチ記事取得中...")
        sponichi_existing_urls = get_existing_urls_for_source('スポニチ')
        sponichi_articles = fetch_all_sponichi_articles(exclude_urls=sponichi_existing_urls)
        all_articles.extend(sponichi_articles)
        print(f"スポニチ記事数: {len(sponichi_articles)}")
        
        # 2. スポーツ報知記事取得
        print("\n2. スポーツ報知記事取得中...")
        hochi_existing_urls = get_existing_urls_for_source('スポーツ報知')
        hochi_articles = []
        for category, url in HOCHI_URLS.items():
            print(f"  {category}記事取得中...")
            category_articles = fetch_hochi_articles(url, exclude_urls=hochi_existing_urls, category=category)
            hochi_articles.extend(category_articles)
        all_articles.extend(hochi_articles)
        print(f"スポーツ報知記事数: {len(hochi_articles)}")
        
        # 3. 日刊スポーツ記事取得
        print("\n3. 日刊スポーツ記事取得中...")
        nikkan_existing_urls = get_existing_urls_for_source('日刊スポーツ')
        nikkan_articles = fetch_all_nikkan_sports_articles(exclude_urls=nikkan_existing_urls)
        all_articles.extend(nikkan_articles)
        print(f"日刊スポーツ記事数: {len(nikkan_articles)}")
        
        # 4. サンスポ記事取得
        print("\n4. サンスポ記事取得中...")
        sanspo_existing_urls = get_existing_urls_for_source('サンスポ')
        sanspo_articles = fetch_all_sanspo_articles(exclude_urls=sanspo_existing_urls)
        all_articles.extend(sanspo_articles)
        print(f"サンスポ記事数: {len(sanspo_articles)}")
        
        # 5. 中日スポーツ記事取得
        print("\n5. 中日スポーツ記事取得中...")
        chunichi_existing_urls = get_existing_urls_for_source('中日スポーツ')
        chunichi_articles = fetch_all_chunichi_articles(exclude_urls=chunichi_existing_urls)
        all_articles.extend(chunichi_articles)
        print(f"中日スポーツ記事数: {len(chunichi_articles)}")
        
        print(f"\n=== 総記事数: {len(all_articles)}件 ===")
        
        if not all_articles:
            print("新しい記事が見つかりませんでした。")
            return
        
        # 6. 高度な重複除去（既存記事との比較含む）
        print("\n6. 高度な重複除去中...")
        unique_articles = smart_deduplicate_articles(all_articles, include_existing_comparison=True)
        print(f"重複除去後記事数: {len(unique_articles)}")
        
        if not unique_articles:
            print("重複除去後、新しい記事が見つかりませんでした。")
            return
        
        # 7. AIコメント抽出（スカウトコメント候補記事のみ）
        print("\n7. AIコメント抽出中...")
        keyword_articles = [a for a in unique_articles if a.get('has_scout_comment_candidate', False)]
        
        if keyword_articles:
            processed_keyword_articles = process_articles_with_ai(keyword_articles)
            print(f"AI処理完了記事数: {len(processed_keyword_articles)}")
        else:
            processed_keyword_articles = []
            print("キーワード該当記事なし")
        
        # 8. AI対象外記事にもscout_comments/scout_rowsをセット
        no_keyword_articles = [a for a in unique_articles if not a.get('has_scout_comment_candidate', False)]
        for a in no_keyword_articles:
            a['scout_comments'] = "スカウトコメント候補なし"
            a['scout_rows'] = []
        
        # 9. 全記事をマージ
        all_processed = processed_keyword_articles + no_keyword_articles

        # 10. 生記事をDBへ保存（URL重複判定の正本）
        print("\n8. 生記事データベース保存中...")
        crawled_results = upsert_crawled_articles(all_processed)
        print(f"  対象件数: {crawled_results['total']}件")
        print(f"  保存件数: {crawled_results['upserted']}件")
        print(f"  エラー件数: {crawled_results['errors']}件")

        # 11. スカウトコメントをデータベースに直接INSERT
        print("\n9. スカウトコメントデータベース挿入中...")
        all_scout_rows = []
        for article in all_processed:
            scout_rows = article.get('scout_rows', [])
            if scout_rows:
                all_scout_rows.extend(scout_rows)
        
        if all_scout_rows:
            print(f"スカウトコメント総数: {len(all_scout_rows)}件")
            try:
                # データベースに直接INSERT（重複排除機能付き）
                insert_results = insert_scout_comments_directly(all_scout_rows)
                print(f"✅ スカウトコメントデータベース挿入完了")
                print(f"  挿入件数: {insert_results['inserted']}件")
                print(f"  重複除外: {insert_results['duplicates']}件")
                print(f"  エラー件数: {insert_results['errors']}件")
                    
            except Exception as e:
                print(f"⚠️ スカウトコメントデータベース挿入エラー: {e}")
                print("Googleスプレッドシートの更新のみ実行します...")
        else:
            print("スカウトコメントが見つかりませんでした。")
        
        # 12. Google Sheets更新
        print("\n10. Google Sheets更新中...")
        update_sheets(all_processed)
        
        print(f"\n=== 既存5社処理完了 ===")
        print(f"総記事数: {len(all_processed)}")
        
        # 結果サマリー
        sources = {}
        scout_comment_count = 0
        attention_signal_count = 0
        for article in all_processed:
            source = article.get('source', '不明')
            sources[source] = sources.get(source, 0) + 1
            scout_comment_count += len(article.get('scout_rows', []))
            attention_signal_count += len(article.get('attention_rows', []))
        
        print("\n=== ソース別記事数 ===")
        for source, count in sources.items():
            print(f"{source}: {count}件")
        
        print(f"\n=== スカウトコメント統計 ===")
        print(f"スカウトコメント総数: {scout_comment_count}件")
        print(f"注目度シグナル総数: {attention_signal_count}件")
        
        # スカウトコメントの内訳
        if scout_comment_count > 0:
            scout_teams = {}
            for article in all_processed:
                for scout_row in article.get('scout_rows', []):
                    if len(scout_row) >= 4:
                        team = scout_row[3]  # スカウト球団名
                        scout_teams[team] = scout_teams.get(team, 0) + 1
            
            print("\n=== 球団別スカウトコメント数 ===")
            for team, count in sorted(scout_teams.items()):
                print(f"{team}: {count}件")
        
        # 実行結果の詳細出力
        print(f"\n=== 実行結果詳細 ===")
        print(f"取得記事数: {len(all_articles)}")
        print(f"最終処理記事数: {len(all_processed)}")
        
    except Exception as e:
        print(f"[エラー] 既存5社メイン処理失敗: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main() 
