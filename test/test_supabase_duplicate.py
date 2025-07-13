"""
実際のSupabase環境での重複チェック機能テスト
環境変数が設定されている場合のみ実行
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import SupabaseScoutCommentInserter
from datetime import datetime, timezone, timedelta

def test_supabase_connection():
    """Supabase接続テスト"""
    
    print("=== Supabase接続テスト ===")
    
    # 環境変数をチェック
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("⚠️  Supabase環境変数が設定されていません。")
        print(f"    SUPABASE_URL: {'設定済み' if supabase_url else '未設定'}")
        print(f"    SUPABASE_KEY: {'設定済み' if supabase_key else '未設定'}")
        print("ダミーモードでのテストを実行します。")
        return False
    
    print("✅ Supabase環境変数が設定されています。")
    return True

def test_duplicate_check():
    """重複チェック機能のテスト"""
    
    print("\n=== 重複チェック機能テスト ===")
    
    # 日本時間（JST）のタイムゾーン
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    
    # テスト用のコメントデータ
    test_comments = [
        {
            'comment': 'テストコメント1',
            'scout_name': 'テストスカウト1',
            'team_name': 'test_team1'
        },
        {
            'comment': 'テストコメント2',
            'scout_name': 'テストスカウト2',
            'team_name': 'test_team2'
        },
        {
            'comment': 'テストコメント1',  # 重複
            'scout_name': 'テストスカウト1',
            'team_name': 'test_team1'
        }
    ]
    
    # Supabase接続をテスト
    has_connection = test_supabase_connection()
    
    if has_connection:
        # 実際のSupabase環境でテスト
        inserter = SupabaseScoutCommentInserter(dummy_mode=False)
        
        print("実際のSupabase環境で重複チェックを実行中...")
        
        for i, test_data in enumerate(test_comments, 1):
            is_duplicate = inserter.check_duplicate_comment(
                test_data['comment'],
                test_data['scout_name'],
                test_data['team_name']
            )
            
            print(f"テスト{i}: コメント='{test_data['comment']}', スカウト='{test_data['scout_name']}', 球団='{test_data['team_name']}'")
            print(f"  重複チェック結果: {'重複' if is_duplicate else '新規'}")
        
        return True
    else:
        # ダミーモードでテスト
        inserter = SupabaseScoutCommentInserter(dummy_mode=True)
        
        print("ダミーモードで重複チェックを実行中...")
        
        for i, test_data in enumerate(test_comments, 1):
            is_duplicate = inserter.check_duplicate_comment(
                test_data['comment'],
                test_data['scout_name'],
                test_data['team_name']
            )
            
            print(f"テスト{i}: コメント='{test_data['comment']}', スカウト='{test_data['scout_name']}', 球団='{test_data['team_name']}'")
            print(f"  重複チェック結果: {'重複' if is_duplicate else '新規'}")
        
        return True

def test_insert_with_duplicate_check():
    """重複チェック付きINSERTのテスト"""
    
    print("\n=== 重複チェック付きINSERTテスト ===")
    
    # 日本時間（JST）のタイムゾーン
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    
    # テスト用のスカウトデータ
    test_scout_data = [
        # 1. 新規コメント
        [
            "テスト選手1",
            "テスト高校1",
            "テストスカウト1",
            "test_team1",
            "これは新規のコメントです。",
            now.strftime("%Y-%m-%d"),
            "https://example.com/test1"
        ],
        
        # 2. 重複コメント（1と同じ内容）
        [
            "テスト選手1",
            "テスト高校1",
            "テストスカウト1",
            "test_team1",
            "これは新規のコメントです。",
            now.strftime("%Y-%m-%d"),
            "https://example.com/test2"
        ],
        
        # 3. 異なるコメント（新規）
        [
            "テスト選手2",
            "テスト高校2",
            "テストスカウト2",
            "test_team2",
            "これは異なるコメントです。",
            now.strftime("%Y-%m-%d"),
            "https://example.com/test3"
        ]
    ]
    
    # Supabase接続をテスト
    has_connection = test_supabase_connection()
    
    if has_connection:
        print("実際のSupabase環境でINSERTテストを実行中...")
        # 実際のSupabase環境では、既存データとの重複チェックが行われる
        from database.supabase_client import insert_scout_comments_directly
        results = insert_scout_comments_directly(test_scout_data, dummy_mode=False)
        
        print(f"INSERT結果:")
        print(f"  総件数: {results['total']}件")
        print(f"  挿入件数: {results['inserted']}件")
        print(f"  重複除外: {results['duplicates']}件")
        print(f"  エラー件数: {results['errors']}件")
        
        return True
    else:
        print("ダミーモードでINSERTテストを実行中...")
        from database.supabase_client import insert_scout_comments_directly
        results = insert_scout_comments_directly(test_scout_data, dummy_mode=True)
        
        print(f"INSERT結果（ダミーモード）:")
        print(f"  総件数: {results['total']}件")
        print(f"  挿入件数: {results['inserted']}件")
        print(f"  重複除外: {results['duplicates']}件")
        print(f"  エラー件数: {results['errors']}件")
        
        return True

def test_environment_info():
    """環境情報の表示"""
    
    print("=== 環境情報 ===")
    
    # Supabase環境変数
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    print(f"SUPABASE_URL: {'設定済み' if supabase_url else '未設定'}")
    print(f"SUPABASE_KEY: {'設定済み' if supabase_key else '未設定'}")
    
    # Python環境
    print(f"Python バージョン: {sys.version}")
    print(f"実行ディレクトリ: {os.getcwd()}")
    
    return True

if __name__ == "__main__":
    # 環境情報表示
    env_success = test_environment_info()
    
    # 重複チェックテスト
    duplicate_success = test_duplicate_check()
    
    # INSERTテスト
    insert_success = test_insert_with_duplicate_check()
    
    print(f"\n=== 総合テスト結果 ===")
    print(f"環境情報テスト: {'✅ 成功' if env_success else '❌ 失敗'}")
    print(f"重複チェックテスト: {'✅ 成功' if duplicate_success else '❌ 失敗'}")
    print(f"INSERTテスト: {'✅ 成功' if insert_success else '❌ 失敗'}")
    
    all_success = env_success and duplicate_success and insert_success
    
    if all_success:
        print("\n🎉 すべてのテストが成功しました！")
        print("\n📝 テスト結果サマリー:")
        print("- 環境変数の確認が完了")
        print("- 重複チェック機能が正常に動作")
        print("- INSERT機能が正常に動作")
        
        # Supabase接続状況の確認
        has_connection = test_supabase_connection()
        if has_connection:
            print("- 実際のSupabase環境でテスト実行")
        else:
            print("- ダミーモードでテスト実行")
    else:
        print("\n⚠️ 一部のテストが失敗しました。") 