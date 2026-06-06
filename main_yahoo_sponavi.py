"""
Yahoo!スポーツナビ専用記事収集・AIコメント抽出システム
1日24回実行（毎時実行）
"""

from typing import List, Dict, Any
from scraper.yahoo_sponavi import YahooSponaviScraper
from ai.gemini import process_articles_with_ai, process_player_candidates_with_ai
from sheets.google_sheets import update_sheets, get_existing_urls_by_source
from database.supabase_client import (
    get_existing_crawled_urls_by_source,
    insert_attention_signals,
    insert_player_candidates,
    insert_scout_comments_directly,
    upsert_crawled_articles,
)
from utils import filter_yahoo_against_existing, smart_deduplicate_articles, annotate_article_signals
from config import YAHOO_SPONAVI_URLS, YAHOO_SPONAVI_MAX_ARTICLES

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
    Yahoo!スポーツナビ専用メイン処理
    """
    print("=== Yahoo!スポーツナビ記事収集システム ===")
    
    all_articles = []
    
    try:
        # Yahoo!スポーツナビ専用スクレイパー
        scraper = YahooSponaviScraper()
        
        # 既存URLを取得（重複回避）
        yahoo_existing_urls = get_existing_urls_for_source('Yahoo!スポーツナビ')
        print(f"[DEBUG] Yahoo!スポーツナビ既存URL数: {len(yahoo_existing_urls)}")
        
        # 各カテゴリの記事を取得
        for category, url in YAHOO_SPONAVI_URLS.items():
            print(f"\n=== {category}記事取得中 ===")
            category_articles = scraper.fetch_article_list(
                category=category, 
                max_articles=YAHOO_SPONAVI_MAX_ARTICLES,
                exclude_urls=yahoo_existing_urls
            )
            
            # 記事の詳細内容を取得
            detailed_articles = []
            for article in category_articles:
                if article.get('url'):
                    title, date, body = scraper.fetch_article_content(article['url'])
                    if title and body:
                        article['title'] = title
                        article['body'] = body
                        article['date'] = date or article.get('date', '')
                        annotate_article_signals(article)
                        detailed_articles.append(article)
                    else:
                        print(f"[DEBUG] 本文取得失敗のため除外: {article.get('url', '')}")
            
            all_articles.extend(detailed_articles)
            print(f"{category}記事数: {len(detailed_articles)}")
        
        print(f"\n=== 総記事数: {len(all_articles)}件 ===")
        
        if not all_articles:
            print("新しい記事が見つかりませんでした。")
            return
        
        # 1. 既存5社の記事との重複チェック（Yahoo独自記事のみ抽出）
        print("\n1. 既存5社記事との重複チェック中...")
        unique_yahoo_articles = filter_yahoo_against_existing(all_articles, threshold=0.7)
        print(f"Yahoo独自記事数: {len(unique_yahoo_articles)}")
        
        # 2. Yahoo記事間の重複除去（既存記事との比較含む）
        print("\n2. Yahoo記事間の重複除去中...")
        deduplicated_articles = smart_deduplicate_articles(
            unique_yahoo_articles, 
            include_existing_comparison=False,
            check_existing_yahoo_urls=False
        )
        print(f"重複除去後記事数: {len(deduplicated_articles)}")
        
        if not deduplicated_articles:
            print("重複除去後、新しい記事が見つかりませんでした。")
            return
        
        # 3. AIコメント抽出（スカウトコメント候補記事のみ）
        print("\n3. AIコメント抽出中...")
        keyword_articles = [a for a in deduplicated_articles if a.get('has_scout_comment_candidate', False)]
        
        if keyword_articles:
            processed_keyword_articles = process_articles_with_ai(keyword_articles)
            print(f"AI処理完了記事数: {len(processed_keyword_articles)}")
        else:
            processed_keyword_articles = []
            print("キーワード該当記事なし")
        
        # 4. AI対象外記事にもscout_comments/scout_rowsをセット
        no_keyword_articles = [a for a in deduplicated_articles if not a.get('has_scout_comment_candidate', False)]
        for a in no_keyword_articles:
            a['scout_comments'] = "スカウトコメント候補なし"
            a['scout_rows'] = []
        
        # 5. 全記事をマージ
        all_processed = processed_keyword_articles + no_keyword_articles

        # 6. 選手候補抽出（未登録候補レビュー用）
        print("\n4. 選手候補抽出中...")
        all_processed = process_player_candidates_with_ai(all_processed)
        player_candidate_count = sum(len(a.get('player_candidate_rows', [])) for a in all_processed)
        print(f"選手候補抽出数: {player_candidate_count}件")

        # 7. 生記事をDBへ保存（URL重複判定の正本）
        print("\n5. 生記事データベース保存中...")
        crawled_results = upsert_crawled_articles(all_processed)
        print(f"  対象件数: {crawled_results['total']}件")
        print(f"  保存件数: {crawled_results['upserted']}件")
        print(f"  エラー件数: {crawled_results['errors']}件")

        # 8. 未登録選手候補・既存選手記事根拠をDBへ保存
        print("\n6. 選手候補データベース保存中...")
        player_candidate_results = insert_player_candidates(all_processed)
        print(f"  対象件数: {player_candidate_results['total']}件")
        print(f"  候補保存件数: {player_candidate_results['inserted']}件")
        print(f"  記事根拠保存件数: {player_candidate_results.get('sources_inserted', 0)}件")
        print(f"  登録済み選手根拠保存件数: {player_candidate_results.get('player_sources_inserted', 0)}件")
        print(f"  登録済み選手検出件数: {player_candidate_results.get('linked_existing_players', 0)}件")
        print(f"  重複除外: {player_candidate_results['duplicates']}件")
        print(f"  エラー件数: {player_candidate_results['errors']}件")

        # 9. 注目度シグナルをDBへ保存
        print("\n7. 注目度シグナルデータベース保存中...")
        attention_results = insert_attention_signals(all_processed)
        print(f"  対象件数: {attention_results['total']}件")
        print(f"  保存件数: {attention_results['inserted']}件")
        print(f"  重複除外: {attention_results['duplicates']}件")
        print(f"  エラー件数: {attention_results['errors']}件")

        # 10. スカウトコメントをデータベースに直接INSERT
        print("\n8. スカウトコメントデータベース挿入中...")
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
        
        # 11. Google Sheets更新
        print("\n9. Google Sheets更新中...")
        update_sheets(all_processed)
        
        print(f"\n=== Yahoo!スポーツナビ処理完了 ===")
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
        print(f"既存5社重複除去後: {len(unique_yahoo_articles)}")
        print(f"最終処理記事数: {len(all_processed)}")
        
    except Exception as e:
        print(f"[エラー] Yahoo!スポーツナビメイン処理失敗: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main() 
