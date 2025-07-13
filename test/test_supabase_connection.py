from dotenv import load_dotenv
load_dotenv()

import os
from supabase import create_client, Client

from database.supabase_client import SupabaseScoutCommentInserter

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

print("SUPABASE_URL:", url)
print("SUPABASE_SERVICE_ROLE_KEY:", "設定済み" if os.getenv("SUPABASE_SERVICE_ROLE_KEY") else "未設定")
print("SUPABASE_KEY:", "設定済み" if os.getenv("SUPABASE_KEY") else "未設定")
print("実際に使うキー:", "service_role" if os.getenv("SUPABASE_SERVICE_ROLE_KEY") else "anon")

if not url or not key:
    print("❌ 環境変数が設定されていません")
    exit(1)

try:
    supabase: Client = create_client(url, key)
    response = supabase.table('scout_comments').select('id').limit(1).execute()
    print("✅ Supabase接続成功")
    print("データ例:", response.data)
except Exception as e:
    print("❌ Supabase接続エラー:", e) 


inserter = SupabaseScoutCommentInserter(dummy_mode=False)
data = {
    'player_id': 'a1632e48-2300-4ac1-b3c3-2bdab2fb53e8',
    'team_name': 'giants',
    'scout_name': '山田太郎',
    'comment': '本番テストコメント',
    'published_at': '2024-06-01T12:00:00',
    'source_url': 'https://example.com/test'
}
result = inserter.insert_scout_comment(data)
print('INSERT結果:', result) 