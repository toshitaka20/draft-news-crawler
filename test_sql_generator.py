#!/usr/bin/env python3
"""
SQL生成機能のテストスクリプト
指定された選手のダミースカウトコメントでテスト
"""

from database.sql_generator import generate_scout_comment_sql
from datetime import datetime

def create_test_scout_comments():
    """テスト用のダミースカウトコメントを作成"""
    
    # 選手名、選手所属チーム、スカウト名、スカウト球団名、コメント内容、記事公開日、記事URL
    test_scout_rows = [
        [
            "榊原 七斗",
            "高校名不明",
            "田中スカウト",
            "giants",
            "榊原は非常に良いピッチャーです。コントロールが抜群で、将来性を感じます。",
            "2025-07-10T15:30:00+09:00",
            "https://example.com/news/sakakibara-naoto-1"
        ],
        [
            "緒方 漣",
            "○○高校",
            "佐藤スカウト",
            "tigers", 
            "緒方選手の打撃センスは素晴らしい。特に右方向への打球が印象的でした。",
            "2025-07-10T14:20:00+09:00",
            "https://example.com/news/ogata-ren-1"
        ],
        [
            "大竹倖太郎",
            "△△高校",
            "山田スカウト",
            "hawks",
            "大竹選手は守備力が高く、内野のどのポジションでもこなせる器用さがある。",
            "2025-07-10T16:45:00+09:00",
            "https://example.com/news/otake-kotaro-1"
        ],
        [
            "榊原七斗",  # スペースなし版でテスト
            "高校名不明",
            "鈴木スカウト",
            "giants",
            "榊原のストレートは威力があり、変化球も効果的。ドラフト候補として注目しています。",
            "2025-07-10T17:00:00+09:00",
            "https://example.com/news/sakakibara-naoto-2"
        ],
        [
            "緒方漣",  # スペースなし版でテスト
            "○○高校",
            "高橋スカウト",
            "other",
            "緒方の長打力は魅力的。今後の成長に期待しています。",
            "2025-07-10T13:15:00+09:00",
            "https://example.com/news/ogata-ren-2"
        ]
    ]
    
    return test_scout_rows

def main():
    """メイン関数"""
    print("=== SQL生成機能テスト ===")
    print("テスト対象選手:")
    print("- 榊原 七斗")
    print("- 緒方 漣")
    print("- 大竹倖太郎")
    print()
    
    # テストデータ作成
    scout_rows = create_test_scout_comments()
    
    print(f"作成したダミーコメント数: {len(scout_rows)}件")
    print()
    
    # 各コメントの内容を表示
    for i, row in enumerate(scout_rows, 1):
        print(f"コメント{i}:")
        print(f"  選手名: {row[0]}")
        print(f"  スカウト: {row[2]} ({row[3]})")
        print(f"  コメント: {row[4][:50]}...")
        print()
    
    # SQL生成実行
    try:
        files = generate_scout_comment_sql(scout_rows)
        print("SQLファイル生成が完了しました！")
        print()
        print("生成されたファイル:")
        for key, filepath in files.items():
            print(f"  {key}: {filepath}")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        raise

if __name__ == "__main__":
    main() 