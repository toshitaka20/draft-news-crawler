import os
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# python-dotenvを使用して.envファイルを読み込む
try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Supabaseライブラリのインポートを条件付きにする
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️  Supabaseライブラリが見つかりません。ダミーモードで動作します。")

class SupabasePlayerLookup:
    """Supabaseを使用した選手ID取得機能"""
    
    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode = dummy_mode or not SUPABASE_AVAILABLE
        
        if not self.dummy_mode:
            self.supabase_url = os.getenv('SUPABASE_URL')
            self.supabase_key = os.getenv('SUPABASE_KEY')  # SUPABASE_KEYに変更
            
            if not self.supabase_url or not self.supabase_key:
                print("⚠️  Supabase環境変数が設定されていません。ダミーモードで動作します。")
                print(f"    SUPABASE_URL: {'設定済み' if self.supabase_url else '未設定'}")
                print(f"    SUPABASE_KEY: {'設定済み' if self.supabase_key else '未設定'}")
                self.dummy_mode = True
            else:
                try:
                    self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
                    print("✅ Supabaseクライアントを初期化しました")
                except Exception as e:
                    print(f"⚠️  Supabase接続エラー: {e}")
                    print("ダミーモードで動作します。")
                    self.dummy_mode = True
        
        self.player_cache = {}  # 選手名 -> player_id のキャッシュ
        
        # ダミーモード用の選手データ
        self.dummy_players = {
            "榊原 七斗": 1001,
            "榊原七斗": 1001,
            "緒方 漣": 1002,
            "緒方漣": 1002,
            "大竹倖太郎": None,  # 未登録選手として扱う
        }
    
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
        normalized = SupabasePlayerLookup.normalize_name(name)
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
    
    def lookup_player_id_dummy(self, player_name: str) -> Optional[int]:
        """ダミーモードでの選手ID取得"""
        variations = self.generate_name_variations(player_name)
        
        for variation in variations:
            if variation in self.dummy_players:
                player_id = self.dummy_players[variation]
                if player_id:
                    print(f"[ダミーモード] {player_name} -> ID: {player_id}")
                else:
                    print(f"[ダミーモード] {player_name} -> 未登録選手")
                return player_id
        
        print(f"[ダミーモード] {player_name} -> 未登録選手")
        return None
    
    def lookup_player_id(self, player_name: str) -> Optional[int]:
        """単一の選手名から選手IDを取得"""
        # キャッシュチェック
        if player_name in self.player_cache:
            return self.player_cache[player_name]
        
        # ダミーモードの場合
        if self.dummy_mode:
            player_id = self.lookup_player_id_dummy(player_name)
            self.player_cache[player_name] = player_id
            return player_id
        
        # 実際のSupabase検索
        variations = self.generate_name_variations(player_name)
        
        try:
            # 各バリエーションで検索
            for priority, variation in enumerate(variations, 1):
                # 完全一致検索
                response = self.supabase.table('players').select('id, name, name_kana').or_(
                    f'name.eq.{variation},name_kana.eq.{variation}'
                ).limit(1).execute()
                
                if response.data:
                    player_id = response.data[0]['id']
                    self.player_cache[player_name] = player_id
                    print(f"[Supabase] {player_name} -> ID: {player_id} (完全一致: {variation})")
                    return player_id
                
                # スペース除去検索（部分一致）
                no_space_variation = variation.replace(' ', '')
                if no_space_variation != variation:
                    response = self.supabase.table('players').select('id, name, name_kana').or_(
                        f'name.ilike.%{no_space_variation}%,name_kana.ilike.%{no_space_variation}%'
                    ).limit(1).execute()
                    
                    if response.data:
                        player_id = response.data[0]['id']
                        self.player_cache[player_name] = player_id
                        print(f"[Supabase] {player_name} -> ID: {player_id} (部分一致: {no_space_variation})")
                        return player_id
            
            # 見つからない場合
            print(f"[Supabase] {player_name} -> 未登録選手")
            self.player_cache[player_name] = None
            return None
            
        except Exception as e:
            print(f"[Supabase検索エラー] {player_name}: {e}")
            self.player_cache[player_name] = None
            return None
    
    def lookup_multiple_players(self, player_names: List[str]) -> Dict[str, Optional[int]]:
        """複数の選手名から選手IDを一括取得"""
        results = {}
        unique_names = list(set(player_names))
        
        mode_text = "ダミーモード" if self.dummy_mode else "Supabase"
        print(f"[{mode_text}] {len(unique_names)}名の選手を検索中...")
        
        for name in unique_names:
            results[name] = self.lookup_player_id(name)
        
        # 結果サマリー
        found_count = sum(1 for pid in results.values() if pid is not None)
        print(f"[{mode_text}] {found_count}/{len(unique_names)}名が登録済み")
        
        return results

class SupabaseScoutCommentGenerator:
    """Supabaseと連携したスカウトコメントSQL生成機能"""
    
    def __init__(self, output_dir: str = "sql_output", dummy_mode: bool = False):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.player_lookup = SupabasePlayerLookup(dummy_mode=dummy_mode)
    
    def generate_insert_sql_with_resolved_ids(self, scout_rows: List[List[str]]) -> str:
        """選手ID解決済みのINSERT SQLを生成"""
        if not scout_rows:
            return ""
        
        # 選手名を抽出
        player_names = [row[0] for row in scout_rows if len(row) > 0]
        
        # 選手IDを一括取得
        player_id_map = self.player_lookup.lookup_multiple_players(player_names)
        
        mode_text = "ダミーモード" if self.player_lookup.dummy_mode else "Supabase連携"
        
        sql_parts = [
            f"-- スカウトコメント INSERT文（選手ID解決済み - {mode_text}）",
            f"-- 生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"-- 選手ID取得結果: {len([p for p in player_id_map.values() if p is not None])}/{len(player_id_map)}名が登録済み",
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
            
            # 選手IDを取得
            player_id = player_id_map.get(player_name)
            
            # 半角スペースを削除してからSQLエスケープ処理
            scout_team = scout_team.strip()
            scout_name = scout_name.strip()
            comment_content = comment_content.strip()
            published_at = published_at.strip()
            article_url = article_url.strip()
            
            escaped_comment = comment_content.replace("'", "''")
            escaped_scout_name = scout_name.replace("'", "''")
            escaped_url = article_url.replace("'", "''")
            
            # 選手IDがある場合とない場合で処理を分ける
            if player_id is not None:
                sql_parts.append(f"""
-- #{i} 選手: {player_name} ({player_team}) - ID: {player_id}
INSERT INTO scout_comments (
    player_id,
    team_name,
    scout_name,
    comment,
    published_at,
    source_url
) VALUES (
    '{player_id}',
    '{scout_team}',
    '{escaped_scout_name}',
    '{escaped_comment}',
    '{published_at}',
    '{escaped_url}'
);""")
            else:
                sql_parts.append(f"""
-- #{i} 選手: {player_name} ({player_team}) - 未登録選手
INSERT INTO scout_comments (
    player_id,
    team_name,
    scout_name,
    comment,
    published_at,
    source_url
) VALUES (
    NULL,
    '{scout_team}',
    '{escaped_scout_name}',
    '{escaped_comment}',
    '{published_at}',
    '{escaped_url}'
);""")
        
        # 統計情報を追加
        registered_count = len([p for p in player_id_map.values() if p is not None])
        unregistered_count = len(player_id_map) - registered_count
        
        sql_parts.extend([
            "",
            "COMMIT;",
            "",
            f"-- 合計 {len(scout_rows)} 件のスカウトコメント",
            f"-- 登録済み選手: {registered_count}名",
            f"-- 未登録選手: {unregistered_count}名",
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
            "-- 未登録選手のコメント一覧",
            "SELECT ",
            "    sc.scout_name,",
            "    sc.team_name,",
            "    LEFT(sc.comment, 100) as comment_preview",
            "FROM scout_comments sc",
            "WHERE sc.player_id IS NULL AND sc.created_at > NOW() - INTERVAL '5 minutes'",
            "ORDER BY sc.created_at DESC;"
        ])
        
        return "\n".join(sql_parts)
    
    def save_sql_file(self, sql_content: str, filename: str) -> str:
        """SQLファイルを保存"""
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(sql_content)
        return filepath
    
    def generate_resolved_sql_file(self, scout_rows: List[List[str]]) -> str:
        """選手ID解決済みSQLファイルを生成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 選手ID解決済みINSERT SQL生成
        insert_sql = self.generate_insert_sql_with_resolved_ids(scout_rows)
        mode_suffix = "dummy" if self.player_lookup.dummy_mode else "supabase"
        filepath = self.save_sql_file(insert_sql, f"scout_comments_resolved_{mode_suffix}_{timestamp}.sql")
        
        print(f"[SQL生成完了] 選手ID解決済みファイル: {filepath}")
        return filepath

def generate_scout_comment_sql_with_resolved_ids(scout_rows: List[List[str]], dummy_mode: bool = False) -> str:
    """メイン関数：選手ID解決済みスカウトコメントSQL生成"""
    generator = SupabaseScoutCommentGenerator(dummy_mode=dummy_mode)
    return generator.generate_resolved_sql_file(scout_rows) 