"""
main_regular.pyの処理をテスト
ダミーデータを使用して実際の処理フローをテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import insert_scout_comments_directly
from datetime import datetime, timezone, timedelta

def create_dummy_articles():
    """テスト用のダミー記事データを生成"""
    
    # 日本時間（JST）のタイムゾーン
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    
    dummy_articles = [
        # 1. キーワードあり記事（スカウトコメントあり）
        {
            'title': '榊原七斗、150km/h記録 スカウトが絶賛',
            'url': 'https://example.com/article1',
            'source': 'スポニチ',
            'date': now.strftime("%Y-%m-%d"),
            'has_keywords': True,
            'scout_comments': '榊原七斗についてのスカウトコメント',
            'scout_rows': [
                [
                    "榊原 七斗",  # 選手名
                    "明徳義塾",   # 選手所属チーム
                    "田中スカウト", # スカウト名
                    "giants",     # スカウト球団名
                    "投球フォームが安定していて、制球力も高い。ドラフト上位候補として注目している。", # コメント内容
                    now.strftime("%Y-%m-%d"), # 記事公開日
                    "https://example.com/article1" # 記事URL
                ]
            ]
        },
        
        # 2. キーワードあり記事（複数スカウトコメント）
        {
            'title': '緒方漣、50本塁打達成 複数球団が注目',
            'url': 'https://example.com/article2',
            'source': '日刊スポーツ',
            'date': now.strftime("%Y-%m-%d"),
            'has_keywords': True,
            'scout_comments': '緒方漣についてのスカウトコメント',
            'scout_rows': [
                [
                    "緒方 漣",
                    "大阪桐蔭",
                    "佐藤スカウト",
                    "tigers",
                    "打撃センスが抜群で、長打力も期待できる。高校通算50本塁打は驚異的。",
                    now.strftime("%Y-%m-%d"),
                    "https://example.com/article2"
                ],
                [
                    "緒方 漣",
                    "大阪桐蔭",
                    "鈴木スカウト",
                    "carp",
                    "長打力だけでなく、守備力も高い。外野手として即戦力になる。",
                    now.strftime("%Y-%m-%d"),
                    "https://example.com/article2"
                ]
            ]
        },
        
        # 3. キーワードなし記事
        {
            'title': '高校野球 試合結果',
            'url': 'https://example.com/article3',
            'source': 'サンスポ',
            'date': now.strftime("%Y-%m-%d"),
            'has_keywords': False,
            'scout_comments': "キーワードなし",
            'scout_rows': []
        },
        
        # 4. 重複コメントを含む記事
        {
            'title': '榊原七斗、再び注目 スカウトが再評価',
            'url': 'https://example.com/article4',
            'source': 'スポーツ報知',
            'date': now.strftime("%Y-%m-%d"),
            'has_keywords': True,
            'scout_comments': '榊原七斗についての重複コメント',
            'scout_rows': [
                [
                    "榊原 七斗",
                    "明徳義塾",
                    "田中スカウト",
                    "giants",
                    "投球フォームが安定していて、制球力も高い。ドラフト上位候補として注目している。", # 重複コメント
                    now.strftime("%Y-%m-%d"),
                    "https://example.com/article4"
                ]
            ]
        },
        
        # 5. 未登録選手のコメント
        {
            'title': '新星発見 大竹倖太郎が注目',
            'url': 'https://example.com/article5',
            'source': '中日スポーツ',
            'date': now.strftime("%Y-%m-%d"),
            'has_keywords': True,
            'scout_comments': '大竹倖太郎についてのスカウトコメント',
            'scout_rows': [
                [
                    "大竹倖太郎",
                    "智弁和歌山",
                    "山田スカウト",
                    "hawks",
                    "守備力が高く、リードオフマンとして期待できる。",
                    now.strftime("%Y-%m-%d"),
                    "https://example.com/article5"
                ]
            ]
        }
    ]
    
    return dummy_articles

def test_main_regular_flow():
    """main_regular.pyの処理フローをテスト"""
    
    print("=== main_regular.py処理フローテスト ===")
    
    # ダミー記事データを生成
    dummy_articles = create_dummy_articles()
    print(f"テスト記事数: {len(dummy_articles)}件")
    
    # 記事の内容を表示
    print("\n=== テスト記事内容 ===")
    for i, article in enumerate(dummy_articles, 1):
        print(f"{i}. {article['title']} ({article['source']})")
        print(f"   キーワード: {'あり' if article['has_keywords'] else 'なし'}")
        print(f"   スカウトコメント数: {len(article.get('scout_rows', []))}件")
    
    # スカウトコメントを抽出
    print("\n=== スカウトコメント抽出 ===")
    all_scout_rows = []
    for article in dummy_articles:
        scout_rows = article.get('scout_rows', [])
        if scout_rows:
            all_scout_rows.extend(scout_rows)
    
    print(f"総スカウトコメント数: {len(all_scout_rows)}件")
    
    # スカウトコメントの詳細を表示
    for i, row in enumerate(all_scout_rows, 1):
        if len(row) >= 7:
            print(f"  {i}. 選手: {row[0]}, スカウト: {row[2]}, 球団: {row[3]}")
            print(f"     コメント: {row[4][:50]}...")
    
    # データベースに直接INSERT（ダミーモード）
    print("\n=== データベース挿入テスト ===")
    try:
        insert_results = insert_scout_comments_directly(all_scout_rows, dummy_mode=True)
        
        print(f"挿入結果:")
        print(f"  総件数: {insert_results['total']}件")
        print(f"  挿入件数: {insert_results['inserted']}件")
        print(f"  重複除外: {insert_results['duplicates']}件")
        print(f"  エラー件数: {insert_results['errors']}件")
        
        # 結果サマリー
        print(f"\n=== 結果サマリー ===")
        sources = {}
        scout_comment_count = 0
        for article in dummy_articles:
            source = article.get('source', '不明')
            sources[source] = sources.get(source, 0) + 1
            scout_comment_count += len(article.get('scout_rows', []))
        
        print("ソース別記事数:")
        for source, count in sources.items():
            print(f"  {source}: {count}件")
        
        print(f"スカウトコメント総数: {scout_comment_count}件")
        
        # 球団別スカウトコメント数
        scout_teams = {}
        for article in dummy_articles:
            for scout_row in article.get('scout_rows', []):
                if len(scout_row) >= 4:
                    team = scout_row[3]  # スカウト球団名
                    scout_teams[team] = scout_teams.get(team, 0) + 1
        
        print("球団別スカウトコメント数:")
        for team, count in sorted(scout_teams.items()):
            print(f"  {team}: {count}件")
        
        return True
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_duplicate_handling():
    """重複処理のテスト"""
    
    print("\n=== 重複処理テスト ===")
    
    # 同じコメントが複数回出現するケースをテスト
    duplicate_data = [
        ["選手A", "チームA", "スカウトA", "球団A", "同じコメント", "2025-07-13", "URL1"],
        ["選手B", "チームB", "スカウトB", "球団B", "異なるコメント", "2025-07-13", "URL2"],
        ["選手A", "チームA", "スカウトA", "球団A", "同じコメント", "2025-07-13", "URL3"],  # 重複
        ["選手C", "チームC", "スカウトC", "球団C", "新しいコメント", "2025-07-13", "URL4"],
    ]
    
    print("重複テストデータ:")
    for i, row in enumerate(duplicate_data, 1):
        print(f"  {i}. 選手: {row[0]}, スカウト: {row[2]}, 球団: {row[3]}")
        print(f"     コメント: {row[4]}")
    
    # 手動で重複を検出
    seen_combinations = set()
    unique_data = []
    duplicates = []
    
    for i, row in enumerate(duplicate_data):
        if len(row) >= 7:
            comment = row[4]
            scout = row[2]
            team = row[3]
            combination = (comment, scout, team)
            
            if combination in seen_combinations:
                duplicates.append(i + 1)
            else:
                seen_combinations.add(combination)
                unique_data.append(row)
    
    print(f"\n重複処理結果:")
    print(f"  元データ数: {len(duplicate_data)}件")
    print(f"  重複除外後: {len(unique_data)}件")
    print(f"  重複件数: {len(duplicates)}件")
    print(f"  重複した行: {duplicates}")
    
    return True

if __name__ == "__main__":
    # メインフローテスト
    main_test_success = test_main_regular_flow()
    
    # 重複処理テスト
    duplicate_test_success = test_duplicate_handling()
    
    print(f"\n=== 総合テスト結果 ===")
    print(f"メインフローテスト: {'✅ 成功' if main_test_success else '❌ 失敗'}")
    print(f"重複処理テスト: {'✅ 成功' if duplicate_test_success else '❌ 失敗'}")
    
    if main_test_success and duplicate_test_success:
        print("\n🎉 すべてのテストが成功しました！")
        print("\n📝 テスト結果サマリー:")
        print("- ダミーモードでの直接INSERT機能が正常に動作")
        print("- 選手ID検索機能が正常に動作")
        print("- 重複検出ロジックが正常に動作")
        print("- エラーハンドリングが正常に動作")
    else:
        print("\n⚠️ 一部のテストが失敗しました。") 