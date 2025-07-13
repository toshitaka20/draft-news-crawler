#!/usr/bin/env python3
"""
RLSポリシー設定テストスクリプト
"""

import os
import sys
from datetime import datetime
from database.supabase_client import SupabaseScoutCommentInserter

def test_rls_policy():
    """RLSポリシー設定をテスト"""
    print("🔍 RLSポリシー設定テスト開始")
    print("=" * 50)
    
    # 環境変数チェック
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    
    print(f"SUPABASE_URL: {'設定済み' if supabase_url else '未設定'}")
    print(f"SUPABASE_KEY: {'設定済み' if supabase_key else '未設定'}")
    
    if not supabase_url or not supabase_key:
        print("❌ 環境変数が設定されていません")
        return False
    
    # インサーターを初期化
    inserter = SupabaseScoutCommentInserter(dummy_mode=False)
    
    if inserter.dummy_mode:
        print("❌ ダミーモードで動作しています")
        return False
    
    # テストデータ
    test_data = {
        'team_name': 'test_team_rls',
        'scout_name': 'test_scout_rls',
        'comment': 'RLSポリシーテストコメント',
        'published_at': datetime.now().isoformat(),
        'source_url': 'https://example.com/rls_test'
    }
    
    print(f"📝 テストデータ: {test_data}")
    
    try:
        # INSERTテスト
        print("\n🔄 INSERTテスト実行中...")
        result = inserter.insert_scout_comment(test_data)
        
        if result:
            print("✅ INSERT成功 - RLSポリシーが正しく設定されています")
            
            # 重複チェックテスト
            print("\n🔄 重複チェックテスト実行中...")
            is_duplicate = inserter.check_duplicate_comment(
                test_data['comment'],
                test_data['scout_name'],
                test_data['team_name']
            )
            
            if is_duplicate:
                print("✅ 重複検出成功 - 重複チェック機能が正常に動作しています")
            else:
                print("⚠️  重複検出失敗 - 重複チェック機能に問題があります")
            
            return True
        else:
            print("❌ INSERT失敗 - RLSポリシーに問題があります")
            return False
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        return False

def test_multiple_inserts():
    """複数INSERTテスト"""
    print("\n🔍 複数INSERTテスト開始")
    print("=" * 50)
    
    inserter = SupabaseScoutCommentInserter(dummy_mode=False)
    
    if inserter.dummy_mode:
        print("❌ ダミーモードで動作しています")
        return False
    
    # テストデータ（複数）
    test_rows = [
        ['test_team_multi', 'test_scout_1', 'テストコメント1', '2024-01-01', 'https://example.com/1'],
        ['test_team_multi', 'test_scout_2', 'テストコメント2', '2024-01-02', 'https://example.com/2'],
        ['test_team_multi', 'test_scout_3', 'テストコメント3', '2024-01-03', 'https://example.com/3'],
    ]
    
    try:
        print(f"📝 {len(test_rows)}件のテストデータをINSERT中...")
        result = inserter.insert_multiple_scout_comments(test_rows)
        
        print(f"✅ 結果: {result}")
        return True
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        return False

def main():
    """メイン関数"""
    print("🚀 RLSポリシー設定テスト")
    print("=" * 50)
    
    # テスト1: 単一INSERT
    test1_result = test_rls_policy()
    
    # テスト2: 複数INSERT
    test2_result = test_multiple_inserts()
    
    print("\n" + "=" * 50)
    print("📊 テスト結果")
    print(f"単一INSERT: {'✅ 成功' if test1_result else '❌ 失敗'}")
    print(f"複数INSERT: {'✅ 成功' if test2_result else '❌ 失敗'}")
    
    if test1_result and test2_result:
        print("\n🎉 すべてのテストが成功しました！")
        print("RLSポリシーが正しく設定されています。")
    else:
        print("\n⚠️  一部のテストが失敗しました。")
        print("RLSポリシーの設定を確認してください。")
        print("参考: docs/RLS_POLICY_SETUP.md")

if __name__ == "__main__":
    main() 