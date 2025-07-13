#!/usr/bin/env python3
"""
環境変数設定確認スクリプト
"""

import os
import sys
from typing import Dict, List

def check_environment_variables() -> Dict[str, bool]:
    """環境変数の設定状況をチェック"""
    required_vars = {
        'SUPABASE_URL': 'Supabase URL',
        'SUPABASE_SERVICE_ROLE_KEY': 'Supabase Service Role Key',
        'SUPABASE_KEY': 'Supabase Anon Key',
        'GEMINI_API_KEY': 'Gemini API Key'
    }
    
    optional_vars = {
        'GOOGLE_SHEETS_CREDENTIALS_FILE': 'Google Sheets Credentials File'
    }
    
    results = {}
    
    print("🔍 環境変数設定確認")
    print("=" * 50)
    
    # 必須環境変数のチェック
    print("\n📋 必須環境変数:")
    for var, description in required_vars.items():
        value = os.getenv(var)
        is_set = value is not None and value.strip() != ''
        results[var] = is_set
        
        status = "✅ 設定済み" if is_set else "❌ 未設定"
        print(f"  {description}: {status}")
        
        if is_set and var.endswith('_KEY') and value:
            # APIキーの形式チェック
            if value.startswith('eyJ') and len(value) > 100:
                print(f"    └─ 形式: 正常 (JWT形式)")
            else:
                print(f"    └─ 形式: 警告 (JWT形式でない可能性)")
    
    # オプション環境変数のチェック
    print("\n📋 オプション環境変数:")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        is_set = value is not None and value.strip() != ''
        results[var] = is_set
        
        status = "✅ 設定済み" if is_set else "⚠️  未設定"
        print(f"  {description}: {status}")
    
    return results

def check_supabase_connection():
    """Supabase接続テスト"""
    print("\n🔗 Supabase接続テスト:")
    print("=" * 30)
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase環境変数が設定されていません")
        return False
    
    try:
        from supabase import create_client, Client
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # 簡単な接続テスト
        response = supabase.table('scout_comments').select('id').limit(1).execute()
        print("✅ Supabase接続成功")
        return True
        
    except Exception as e:
        print(f"❌ Supabase接続エラー: {e}")
        return False

def check_rls_policy():
    """RLSポリシー設定確認"""
    print("\n🔒 RLSポリシー設定確認:")
    print("=" * 30)
    
    try:
        from database.supabase_client import SupabaseScoutCommentInserter
        inserter = SupabaseScoutCommentInserter(dummy_mode=False)
        
        if inserter.dummy_mode:
            print("❌ ダミーモードで動作しています")
            return False
        
        # テスト用データ
        test_data = {
            'team_name': 'test_env_check',
            'scout_name': 'test_scout_env',
            'comment': '環境変数確認テスト',
            'published_at': '2024-01-01T00:00:00',
            'source_url': 'https://example.com/env_check'
        }
        
        # INSERTテスト
        result = inserter.insert_scout_comment(test_data)
        
        if result:
            print("✅ RLSポリシー設定正常 - INSERT成功")
            
            # テストデータを削除
            try:
                inserter.supabase.table('scout_comments').delete().eq('team_name', 'test_env_check').eq('scout_name', 'test_scout_env').execute()
                print("✅ テストデータ削除完了")
            except:
                print("⚠️  テストデータ削除に失敗（手動で削除してください）")
            
            return True
        else:
            print("❌ RLSポリシー設定に問題があります")
            return False
            
    except Exception as e:
        print(f"❌ RLSポリシーテストエラー: {e}")
        return False

def provide_setup_instructions():
    """設定手順を表示"""
    print("\n📖 設定手順:")
    print("=" * 30)
    
    print("1. Supabase設定:")
    print("   - Supabase Dashboard → Settings → API")
    print("   - Project URL をコピー")
    print("   - service_role キーをコピー")
    print("   - anon キーをコピー")
    
    print("\n2. 環境変数設定:")
    print("   - プロジェクトルートに .env ファイルを作成")
    print("   - env.example を参考に設定")
    
    print("\n3. RLSポリシー設定:")
    print("   - Supabase Dashboard → SQL Editor")
    print("   - database/supabase_rls_policies.sql を実行")
    
    print("\n4. テスト実行:")
    print("   - python test/test_rls_policy.py")
    print("   - python test/check_env.py")

def main():
    """メイン関数"""
    print("🚀 環境変数設定確認ツール")
    print("=" * 50)
    
    # 環境変数チェック
    env_results = check_environment_variables()
    
    # Supabase接続テスト
    connection_ok = check_supabase_connection()
    
    # RLSポリシーテスト
    rls_ok = check_rls_policy()
    
    # 結果サマリー
    print("\n" + "=" * 50)
    print("📊 結果サマリー:")
    
    required_vars_ok = all(env_results.get(var, False) for var in ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY', 'SUPABASE_KEY'])
    
    print(f"環境変数: {'✅ 正常' if required_vars_ok else '❌ 問題あり'}")
    print(f"Supabase接続: {'✅ 正常' if connection_ok else '❌ 問題あり'}")
    print(f"RLSポリシー: {'✅ 正常' if rls_ok else '❌ 問題あり'}")
    
    if required_vars_ok and connection_ok and rls_ok:
        print("\n🎉 すべての設定が正常です！")
        print("スカウトコメントのINSERTが正常に動作します。")
    else:
        print("\n⚠️  設定に問題があります。")
        print("以下の手順で設定を確認してください。")
        provide_setup_instructions()

if __name__ == "__main__":
    main() 