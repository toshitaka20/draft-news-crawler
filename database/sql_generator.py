import os
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime

class PlayerNameMatcher:
    """選手名の表記揺れに対応したマッチング機能"""
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """選手名を正規化"""
        if not name:
            return ""
        
        # 全角・半角の統一
        name = name.replace('　', ' ')  # 全角スペースを半角に
        name = re.sub(r'\s+', ' ', name)  # 複数スペースを1つに
        name = name.strip()
        
        return name
    
    @staticmethod
    def generate_name_variations(name: str) -> List[str]:
        """選手名のバリエーションを生成"""
        normalized = PlayerNameMatcher.normalize_name(name)
        variations = []
        
        # 1. 元の名前
        variations.append(normalized)
        
        # 2. スペースなし版
        no_space = normalized.replace(' ', '')
        if no_space != normalized:
            variations.append(no_space)
        
        # 3. スペースあり版（元々スペースがない場合）
        if ' ' not in normalized and len(normalized) >= 2:
            # 一般的な分割パターンを試行
            for i in range(1, len(normalized)):
                spaced = normalized[:i] + ' ' + normalized[i:]
                variations.append(spaced)
        
        return list(set(variations))  # 重複除去

class SQLGeneratorWithPlayerLookup:
    def __init__(self, output_dir: str = "sql_output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.matcher = PlayerNameMatcher()
        self.player_id_cache = {}  # 選手名 -> player_id のキャッシュ
    
    def generate_player_lookup_query(self, name: str) -> str:
        """単一の選手名に対する検索クエリを生成"""
        variations = self.matcher.generate_name_variations(name)
        conditions = []
        
        for var in variations:
            escaped_var = var.replace("'", "''")
            conditions.extend([
                f"name = '{escaped_var}'",
                f"name_kana = '{escaped_var}'",
                f"REPLACE(name, ' ', '') = '{var.replace(' ', '')}'",
                f"REPLACE(name_kana, ' ', '') = '{var.replace(' ', '')}'"
            ])
        
        return f"""
SELECT 
    id,
    name,
    name_kana,
    team_name,
    CASE 
        WHEN name = '{name}' OR name_kana = '{name}' THEN 1
        WHEN REPLACE(name, ' ', '') = '{name.replace(' ', '')}' OR REPLACE(name_kana, ' ', '') = '{name.replace(' ', '')}' THEN 2
        ELSE 3
    END as match_priority
FROM players 
WHERE {' OR '.join(conditions)}
ORDER BY match_priority
LIMIT 1;"""
    
    def generate_player_lookup_sql(self, player_names: List[str]) -> str:
        """全選手の検索SQLを生成"""
        unique_names = list(set(player_names))
        
        sql_parts = [
            "-- 選手ID検索SQL（自動マッチング用）",
            f"-- 生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "-- このSQLを実行して選手IDを確認してください",
            ""
        ]
        
        for name in unique_names:
            variations = self.matcher.generate_name_variations(name)
            sql_parts.append(f"-- 選手名: '{name}' (バリエーション: {variations})")
            sql_parts.append(self.generate_player_lookup_query(name))
            sql_parts.append("")
        
        return "\n".join(sql_parts)
    
    def create_player_id_mapping_sql(self, player_names: List[str]) -> str:
        """選手IDマッピング用のSQLを生成"""
        unique_names = list(set(player_names))
        
        sql_parts = [
            "-- 選手IDマッピング作成SQL",
            f"-- 生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "-- このSQLを実行して player_id_mapping ビューを作成",
            "",
            "DROP VIEW IF EXISTS player_id_mapping;",
            "CREATE VIEW player_id_mapping AS",
            "SELECT * FROM (",
        ]
        
        union_parts = []
        for i, name in enumerate(unique_names):
            variations = self.matcher.generate_name_variations(name)
            conditions = []
            
            for var in variations:
                escaped_var = var.replace("'", "''")
                conditions.extend([
                    f"name = '{escaped_var}'",
                    f"name_kana = '{escaped_var}'",
                    f"REPLACE(name, ' ', '') = '{var.replace(' ', '')}'",
                    f"REPLACE(name_kana, ' ', '') = '{var.replace(' ', '')}'"
                ])
            
            union_part = f"""
    SELECT 
        '{name.replace("'", "''")}' as original_name,
        (
            SELECT id 
            FROM players 
            WHERE {' OR '.join(conditions)}
            ORDER BY 
                CASE 
                    WHEN name = '{name}' OR name_kana = '{name}' THEN 1
                    WHEN REPLACE(name, ' ', '') = '{name.replace(' ', '')}' OR REPLACE(name_kana, ' ', '') = '{name.replace(' ', '')}' THEN 2
                    ELSE 3
                END
            LIMIT 1
        ) as player_id"""
            
            union_parts.append(union_part)
        
        sql_parts.append("    UNION ALL".join(union_parts))
        sql_parts.extend([
            ") mapping;",
            "",
            "-- 確認用クエリ",
            "SELECT ",
            "    original_name,",
            "    player_id,",
            "    CASE WHEN player_id IS NULL THEN '未登録' ELSE '登録済み' END as status",
            "FROM player_id_mapping",
            "ORDER BY original_name;",
            ""
        ])
        
        return "\n".join(sql_parts)
    
    def generate_insert_sql(self, scout_rows: List[List[str]]) -> str:
        """スカウトコメントINSERT SQLを生成（player_id自動取得版）"""
        if not scout_rows:
            return ""
        
        sql_parts = [
            "-- スカウトコメント INSERT文（player_id自動取得版）",
            f"-- 生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "-- 前提: player_id_mapping ビューが作成済みであること",
            "",
            "BEGIN;",
            ""
        ]
        
        for i, row in enumerate(scout_rows, 1):
            if len(row) < 7:
                continue
                
            player_name = row[0]
            player_team = row[1]
            scout_name = row[2]
            scout_team = row[3]
            comment_content = row[4]
            published_at = row[5]
            article_url = row[6]
            
            # SQLエスケープ処理
            escaped_player_name = player_name.replace("'", "''")
            escaped_comment = comment_content.replace("'", "''")
            escaped_scout_name = scout_name.replace("'", "''")
            escaped_url = article_url.replace("'", "''")
            
            sql_parts.append(f"""
-- #{i} 選手: {player_name} ({player_team})
INSERT INTO scout_comments (
    player_id,
    team_name,
    scout_name,
    comment,
    published_at,
    source_url
) VALUES (
    (SELECT player_id FROM player_id_mapping WHERE original_name = '{escaped_player_name}'),
    '{scout_team}',
    '{escaped_scout_name}',
    '{escaped_comment}',
    '{published_at}',
    '{escaped_url}'
);""")
        
        sql_parts.extend([
            "",
            "COMMIT;",
            "",
            f"-- 合計 {len(scout_rows)} 件のスカウトコメント",
            "",
            "-- 結果確認クエリ",
            "SELECT ",
            "    sc.id,",
            "    COALESCE(p.name, '未登録選手') as player_name,",
            "    sc.team_name,",
            "    sc.scout_name,",
            "    LEFT(sc.comment, 50) as comment_preview,",
            "    sc.published_at",
            "FROM scout_comments sc",
            "LEFT JOIN players p ON sc.player_id = p.id",
            "WHERE sc.created_at > NOW() - INTERVAL '5 minutes'",
            "ORDER BY sc.created_at DESC;",
            "",
            "-- 未登録選手のコメント確認",
            "SELECT COUNT(*) as unregistered_player_comments",
            "FROM scout_comments",
            "WHERE player_id IS NULL AND created_at > NOW() - INTERVAL '5 minutes';"
        ])
        
        return "\n".join(sql_parts)
    
    def save_sql_file(self, sql_content: str, filename: str) -> str:
        """SQLファイルを保存"""
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(sql_content)
        return filepath
    
    def generate_all_sql_files(self, scout_rows: List[List[str]]) -> Dict[str, str]:
        """全SQLファイルを生成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files = {}
        
        # 選手名を抽出
        player_names = [row[0] for row in scout_rows if len(row) > 0]
        
        # 1. 選手検索SQL（確認用）
        lookup_sql = self.generate_player_lookup_sql(player_names)
        files['lookup'] = self.save_sql_file(lookup_sql, f"01_player_lookup_{timestamp}.sql")
        
        # 2. マッピングビュー作成SQL
        mapping_sql = self.create_player_id_mapping_sql(player_names)
        files['mapping'] = self.save_sql_file(mapping_sql, f"02_player_mapping_{timestamp}.sql")
        
        # 3. INSERT SQL
        insert_sql = self.generate_insert_sql(scout_rows)
        files['insert'] = self.save_sql_file(insert_sql, f"03_scout_comments_insert_{timestamp}.sql")
        
        return files

def generate_scout_comment_sql(scout_rows: List[List[str]]) -> Dict[str, str]:
    """メイン関数：選手ID自動取得版スカウトコメントSQL生成"""
    generator = SQLGeneratorWithPlayerLookup()
    files = generator.generate_all_sql_files(scout_rows)
    
    print(f"[SQL生成] 以下のファイルを生成しました:")
    print(f"  1. 選手検索確認SQL: {files['lookup']}")
    print(f"  2. マッピングビュー作成SQL: {files['mapping']}")
    print(f"  3. INSERT SQL: {files['insert']}")
    print(f"")
    print(f"[実行手順]")
    print(f"  1. {files['lookup']} で選手マッチング結果を確認（任意）")
    print(f"  2. {files['mapping']} を実行してマッピングビューを作成")
    print(f"  3. {files['insert']} を実行（登録済み選手は自動でID設定、未登録はNULL）")
    
    return files 