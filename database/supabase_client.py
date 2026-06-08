import os
import re
import json
import hashlib
from typing import List, Dict, Optional, Tuple, Any, Set
from datetime import datetime, timezone, timedelta

# 日本時間（JST）のタイムゾーン
JST = timezone(timedelta(hours=9))

def now_jst() -> datetime:
    """日本時間での現在時刻を取得"""
    return datetime.now(JST)

def _init_supabase_client(dummy_mode: bool = False) -> Tuple[bool, Optional["Client"]]:
    """Supabaseクライアントを初期化し、(dummy_mode, client) を返す。"""
    is_dummy = dummy_mode or not SUPABASE_AVAILABLE

    if is_dummy:
        return True, None

    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')

    if not supabase_url or not supabase_key:
        print("⚠️  Supabase環境変数が設定されていません。ダミーモードで動作します。")
        print(f"    SUPABASE_URL: {'設定済み' if supabase_url else '未設定'}")
        print(f"    SUPABASE_KEY: {'設定済み' if supabase_key else '未設定'}")
        return True, None

    try:
        return False, create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"⚠️  Supabase接続エラー: {e}")
        print("ダミーモードで動作します。")
        return True, None

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

class SupabaseCrawledArticleStore:
    """crawled_articles を使った生記事保存・URL重複判定。"""

    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode, self.supabase = _init_supabase_client(dummy_mode=dummy_mode)
        if not self.dummy_mode:
            print("✅ Supabaseクライアントを初期化しました（crawled_articles）")

    @staticmethod
    def calculate_content_hash(title: str, body: str) -> str:
        normalized = re.sub(r'\s+', ' ', f"{title or ''}\n{body or ''}".strip())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    @staticmethod
    def _format_published_at(date_value: str) -> Optional[str]:
        if not date_value:
            return None

        try:
            from utils import format_timestamp
            formatted = format_timestamp(date_value)
            return formatted or None
        except Exception:
            return date_value

    @staticmethod
    def _to_record(article: Dict[str, Any]) -> Dict[str, Any]:
        title = article.get('title', '') or ''
        body = article.get('body', '') or ''
        return {
            'source': article.get('source', '') or '不明',
            'category': article.get('category', ''),
            'url': article.get('url', ''),
            'title': title,
            'body': body,
            'published_at': SupabaseCrawledArticleStore._format_published_at(article.get('date', '') or ''),
            'has_scout_comment_candidate': bool(article.get('has_scout_comment_candidate', False)),
            'has_attention_candidate': bool(article.get('has_attention_candidate', False)),
            'has_player_candidate': bool(article.get('has_player_candidate', False)),
            'content_hash': SupabaseCrawledArticleStore.calculate_content_hash(title, body),
            'raw': {
                'date': article.get('date', ''),
                'scout_comments': article.get('scout_comments', ''),
                'attention_rows': article.get('attention_rows', []),
                'player_candidate_rows': article.get('player_candidate_rows', []),
            },
        }

    def get_existing_urls_by_source(self, source: str) -> Set[str]:
        if self.dummy_mode or self.supabase is None:
            print(f"[DB] crawled_articles URL取得スキップ（ダミーモード）: {source}")
            return set()

        try:
            response = (
                self.supabase
                .table('crawled_articles')
                .select('url')
                .eq('source', source)
                .execute()
            )
            urls = {row['url'] for row in (response.data or []) if row.get('url')}
            print(f"[DB] crawled_articles 既存URL数 ({source}): {len(urls)}")
            return urls
        except Exception as e:
            print(f"[DB] crawled_articles 既存URL取得エラー ({source}): {e}")
            return set()

    def get_existing_urls(self) -> Set[str]:
        if self.dummy_mode or self.supabase is None:
            print("[DB] crawled_articles URL取得スキップ（ダミーモード）")
            return set()

        try:
            response = self.supabase.table('crawled_articles').select('url').execute()
            urls = {row['url'] for row in (response.data or []) if row.get('url')}
            print(f"[DB] crawled_articles 既存URL数: {len(urls)}")
            return urls
        except Exception as e:
            print(f"[DB] crawled_articles 既存URL取得エラー: {e}")
            return set()

    def upsert_articles(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        if not articles:
            return {'total': 0, 'upserted': 0, 'errors': 0}

        if self.dummy_mode or self.supabase is None:
            print(f"[DB] crawled_articles 保存スキップ（ダミーモード）: {len(articles)}件")
            return {'total': len(articles), 'upserted': 0, 'errors': 0}

        records = []
        for article in articles:
            record = self._to_record(article)
            if record['url'] and record['title']:
                records.append(record)

        if not records:
            return {'total': len(articles), 'upserted': 0, 'errors': len(articles)}

        try:
            response = (
                self.supabase
                .table('crawled_articles')
                .upsert(records, on_conflict='url')
                .execute()
            )
            upserted = len(response.data or records)
            print(f"[DB] crawled_articles 保存完了: {upserted}件")
            return {'total': len(articles), 'upserted': upserted, 'errors': 0}
        except Exception as e:
            print(f"[DB] crawled_articles 保存エラー: {e}")
            return {'total': len(articles), 'upserted': 0, 'errors': len(articles)}

    def get_article_id_map_by_urls(self, urls: List[str]) -> Dict[str, str]:
        if self.dummy_mode or self.supabase is None or not urls:
            return {}

        unique_urls = sorted({url for url in urls if url})
        try:
            response = (
                self.supabase
                .table('crawled_articles')
                .select('id,url')
                .in_('url', unique_urls)
                .execute()
            )
            return {
                row['url']: row['id']
                for row in (response.data or [])
                if row.get('url') and row.get('id')
            }
        except Exception as e:
            print(f"[DB] crawled_articles ID取得エラー: {e}")
            return {}

class SupabasePlayerLookup:
    """Supabaseを使用した選手ID取得機能"""
    
    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode = dummy_mode or not SUPABASE_AVAILABLE
        
        if not self.dummy_mode:
            self.supabase_url = os.getenv('SUPABASE_URL')
            # サービスロールキーを優先、なければ通常のキーを使用
            self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
            
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

class SupabasePlayerCandidateStore:
    """player_candidates への未登録選手候補保存。"""

    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode, self.supabase = _init_supabase_client(dummy_mode=dummy_mode)
        self.player_lookup = SupabasePlayerLookup(dummy_mode=dummy_mode)
        if not self.dummy_mode:
            print("✅ Supabaseクライアントを初期化しました（player_candidates）")

    @staticmethod
    def _clean_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        if value in (None, ''):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_confidence(value: Any) -> Optional[float]:
        if value in (None, ''):
            return None
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _normalize_category(value: Any) -> Optional[str]:
        text = SupabasePlayerCandidateStore._clean_text(value)
        if not text:
            return None
        if '高校' in text:
            return '高校'
        if '大学' in text:
            return '大学'
        if '社会人' in text:
            return '社会人'
        if '独立' in text:
            return '独立リーグ'
        return text

    @staticmethod
    def _published_year(row: Dict[str, Any]) -> Optional[int]:
        published_at = str(row.get('published_at') or row.get('date') or '')
        match = re.search(r'(20\d{2})', published_at)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _extract_year_number(value: Any) -> Optional[int]:
        text = SupabasePlayerCandidateStore._clean_text(value)
        if not text:
            return None
        match = re.search(r'(\d+)\s*年', text)
        if match:
            return int(match.group(1))
        return SupabasePlayerCandidateStore._to_int(text)

    @staticmethod
    def _infer_draft_year(row: Dict[str, Any]) -> Optional[int]:
        draft_year = SupabasePlayerCandidateStore._to_int(row.get('draft_year'))
        if draft_year:
            return draft_year

        published_year = SupabasePlayerCandidateStore._published_year(row)
        school_year = SupabasePlayerCandidateStore._extract_year_number(row.get('school_year'))
        if not published_year:
            return None

        category = SupabasePlayerCandidateStore._normalize_category(
            row.get('category') or row.get('article_category')
        )
        school_year_text = SupabasePlayerCandidateStore._clean_text(row.get('school_year')) or ''

        target_year = None
        if school_year:
            if category == '高校':
                target_year = 3
            elif category == '大学':
                target_year = 4
            elif category == '社会人':
                if '高卒' in school_year_text:
                    target_year = 3
                elif '大卒' in school_year_text:
                    target_year = 2
                elif school_year in (2, 3):
                    target_year = school_year

        if target_year:
            return published_year + max(target_year - school_year, 0)

        draft_context = ' '.join(
            str(row.get(key) or '')
            for key in ('school_year', 'description', 'evidence', 'source_title')
        )
        if re.search(r'来年(?:の)?ドラフト', draft_context):
            return published_year + 1
        if re.search(r'今秋ドラフト|今年(?:の)?ドラフト|今ドラフト', draft_context):
            return published_year

        return None

    @staticmethod
    def _normalize_positions(value: Any) -> List[str]:
        if value in (None, ''):
            return []
        if isinstance(value, list):
            raw_values = value
        else:
            text = str(value)
            raw_values = re.split(r'[,、/・\s]+', text)

        positions: List[str] = []
        aliases = [
            ('投手', ('投手', 'ピッチャー', 'P')),
            ('捕手', ('捕手', 'キャッチャー', 'C')),
            ('内野手', ('内野手', '一塁手', '二塁手', '三塁手', '遊撃手', 'ファースト', 'セカンド', 'サード', 'ショート', 'IF')),
            ('外野手', ('外野手', '左翼手', '中堅手', '右翼手', 'レフト', 'センター', 'ライト', 'OF')),
        ]

        for raw in raw_values:
            text = SupabasePlayerCandidateStore._clean_text(raw)
            if not text:
                continue
            normalized = None
            for canonical, words in aliases:
                if any(word in text for word in words):
                    normalized = canonical
                    break
            normalized = normalized or text
            if normalized not in positions:
                positions.append(normalized)

        return positions

    @staticmethod
    def _normalize_throw(value: Any) -> Optional[str]:
        text = SupabasePlayerCandidateStore._clean_text(value)
        if not text:
            return None
        upper = text.upper()
        if upper == 'R' or '右' in text:
            return 'R'
        if upper == 'L' or '左' in text:
            return 'L'
        return None

    @staticmethod
    def _normalize_bat(value: Any) -> Optional[str]:
        text = SupabasePlayerCandidateStore._clean_text(value)
        if not text:
            return None
        upper = text.upper()
        if upper == 'S' or '両' in text or 'スイッチ' in text:
            return 'S'
        if upper == 'R' or '右' in text:
            return 'R'
        if upper == 'L' or '左' in text:
            return 'L'
        return None

    @staticmethod
    def _candidate_key(name: str, team: Optional[str], draft_year: Optional[int]) -> Tuple[str, str, int]:
        return (name, team or '', draft_year or 0)

    def _get_existing_candidates(self, rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str, int], str]:
        if self.dummy_mode or self.supabase is None or not rows:
            return {}

        names = sorted({row.get('name') for row in rows if row.get('name')})
        if not names:
            return {}

        try:
            response = (
                self.supabase
                .table('player_candidates')
                .select('id,name,team,team_name,draft_year')
                .in_('name', names)
                .execute()
            )
            return {
                self._candidate_key(
                    row.get('name') or '',
                    row.get('team') or row.get('team_name'),
                    self._to_int(row.get('draft_year')),
                ): row['id']
                for row in (response.data or [])
                if row.get('id') and row.get('name')
            }
        except Exception as e:
            print(f"[DB] player_candidates 既存取得エラー: {e}")
            return {}

    def _get_existing_source_keys(self, source_urls: List[str]) -> Set[Tuple[str, str, str]]:
        if self.dummy_mode or self.supabase is None or not source_urls:
            return set()

        try:
            response = (
                self.supabase
                .table('player_candidate_sources')
                .select('player_candidate_id,source_url,evidence')
                .in_('source_url', sorted(set(source_urls)))
                .execute()
            )
            return {
                (
                    row.get('player_candidate_id') or '',
                    row.get('source_url') or '',
                    row.get('evidence') or '',
                )
                for row in (response.data or [])
            }
        except Exception as e:
            print(f"[DB] player_candidate_sources 既存取得エラー: {e}")
            return set()

    def _get_existing_player_source_keys(self, source_urls: List[str]) -> Set[Tuple[str, str, str]]:
        if self.dummy_mode or self.supabase is None or not source_urls:
            return set()

        try:
            response = (
                self.supabase
                .table('player_article_sources')
                .select('player_id,source_url,evidence')
                .in_('source_url', sorted(set(source_urls)))
                .execute()
            )
            return {
                (
                    row.get('player_id') or '',
                    row.get('source_url') or '',
                    row.get('evidence') or '',
                )
                for row in (response.data or [])
            }
        except Exception as e:
            print(f"[DB] player_article_sources 既存取得エラー: {e}")
            return set()

    def insert_unregistered_candidates(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        rows = []
        for article in articles:
            rows.extend(article.get('player_candidate_rows', []))

        if not rows:
            return {
                'total': 0,
                'inserted': 0,
                'sources_inserted': 0,
                'player_sources_inserted': 0,
                'linked_existing_players': 0,
                'skipped_existing_players': 0,
                'duplicates': 0,
                'errors': 0,
            }

        if self.dummy_mode or self.supabase is None:
            print(f"[DB] player_candidates 保存スキップ（ダミーモード）: {len(rows)}件")
            return {
                'total': len(rows),
                'inserted': 0,
                'sources_inserted': 0,
                'player_sources_inserted': 0,
                'linked_existing_players': 0,
                'skipped_existing_players': 0,
                'duplicates': 0,
                'errors': 0,
            }

        source_urls = [row.get('source_url', '') for row in rows if row.get('source_url')]
        crawled_id_map = SupabaseCrawledArticleStore(dummy_mode=False).get_article_id_map_by_urls(source_urls)
        player_id_map = self.player_lookup.lookup_multiple_players([row.get('name', '') for row in rows])

        candidate_inputs = []
        player_source_inputs = []
        linked_existing_players = 0
        duplicates = 0

        for row in rows:
            name = self._clean_text(row.get('name'))
            source_url = self._clean_text(row.get('source_url'))
            if not name or not source_url:
                continue

            player_id = player_id_map.get(name)
            if player_id is not None:
                linked_existing_players += 1
                player_source_inputs.append((str(player_id), row))
                continue

            team_name = self._clean_text(row.get('team_name'))
            team = self._clean_text(row.get('team')) or team_name
            category = self._normalize_category(row.get('category') or row.get('article_category'))
            draft_year = self._infer_draft_year(row)
            positions = self._normalize_positions(row.get('positions') or row.get('position'))
            key = self._candidate_key(name, team, draft_year)
            candidate_inputs.append((key, row, {
                'player_id': None,
                'name': name,
                'name_kana': self._clean_text(row.get('name_kana')),
                'team': team,
                'team_name': team_name,
                'category': category,
                'draft_year': draft_year,
                'school_year': self._clean_text(row.get('school_year')),
                'positions': positions,
                'throws': self._normalize_throw(row.get('throws')),
                'bats': self._normalize_bat(row.get('bats')),
                'height_cm': self._to_int(row.get('height_cm')),
                'weight_kg': self._to_int(row.get('weight_kg')),
                'birth_date': self._clean_text(row.get('birth_date')),
                'fastball_max': self._to_int(row.get('fastball_max')),
                'description': self._clean_text(row.get('description')),
                'source_count': 0,
                'latest_source_url': source_url,
                'latest_source_title': self._clean_text(row.get('source_title')),
                'latest_evidence': self._clean_text(row.get('evidence')),
                'latest_confidence': self._to_confidence(row.get('confidence')),
                'status': 'pending',
                'extracted_raw': row.get('extracted_raw') or row,
            }))

        existing_candidates = self._get_existing_candidates([item[2] for item in candidate_inputs])
        candidate_records = []
        seen_candidate_keys: Set[Tuple[str, str, int]] = set()
        for key, _row, record in candidate_inputs:
            if key in existing_candidates or key in seen_candidate_keys:
                duplicates += 1
                continue
            seen_candidate_keys.add(key)
            candidate_records.append(record)

        inserted = 0
        try:
            if candidate_records:
                response = self.supabase.table('player_candidates').insert(candidate_records).execute()
                inserted_rows = response.data or candidate_records
                inserted = len(inserted_rows)
                for row in inserted_rows:
                    if row.get('id') and row.get('name'):
                        key = self._candidate_key(
                            row.get('name') or '',
                            row.get('team') or row.get('team_name'),
                            self._to_int(row.get('draft_year')),
                        )
                        existing_candidates[key] = row['id']
                print(f"[DB] player_candidates 保存完了: {inserted}件")
                existing_candidates.update(self._get_existing_candidates([item[2] for item in candidate_inputs]))
        except Exception as e:
            print(f"[DB] player_candidates 保存エラー: {e}")
            return {
                'total': len(rows),
                'inserted': 0,
                'sources_inserted': 0,
                'player_sources_inserted': 0,
                'linked_existing_players': linked_existing_players,
                'skipped_existing_players': linked_existing_players,
                'duplicates': duplicates,
                'errors': len(candidate_records),
            }

        source_records = []
        seen_source_keys: Set[Tuple[str, str, str]] = set()
        existing_source_keys = self._get_existing_source_keys(source_urls)
        for key, row, _record in candidate_inputs:
            candidate_id = existing_candidates.get(key)
            source_url = self._clean_text(row.get('source_url'))
            if not candidate_id or not source_url:
                continue

            evidence = self._clean_text(row.get('evidence'))
            source_key = (candidate_id, source_url, evidence or '')
            if source_key in seen_source_keys or source_key in existing_source_keys:
                duplicates += 1
                continue
            seen_source_keys.add(source_key)

            source_records.append({
                'player_candidate_id': candidate_id,
                'crawled_article_id': crawled_id_map.get(source_url),
                'source_url': source_url,
                'source_title': self._clean_text(row.get('source_title')),
                'published_at': SupabaseCrawledArticleStore._format_published_at(row.get('published_at') or ''),
                'source': self._clean_text(row.get('source')),
                'category': self._clean_text(row.get('article_category') or row.get('category')),
                'evidence': evidence,
                'confidence': self._to_confidence(row.get('confidence')),
                'extracted_raw': row.get('extracted_raw') or row,
            })

        sources_inserted = 0
        try:
            if source_records:
                response = self.supabase.table('player_candidate_sources').insert(source_records).execute()
                sources_inserted = len(response.data or source_records)
                print(f"[DB] player_candidate_sources 保存完了: {sources_inserted}件")
        except Exception as e:
            print(f"[DB] player_candidate_sources 保存エラー: {e}")
            return {
                'total': len(rows),
                'inserted': inserted,
                'sources_inserted': 0,
                'player_sources_inserted': 0,
                'linked_existing_players': linked_existing_players,
                'skipped_existing_players': linked_existing_players,
                'duplicates': duplicates,
                'errors': len(source_records),
            }

        self._refresh_candidate_source_summaries(sorted({record['player_candidate_id'] for record in source_records}))

        player_source_records = []
        seen_player_source_keys: Set[Tuple[str, str, str]] = set()
        existing_player_source_keys = self._get_existing_player_source_keys(source_urls)
        for player_id, row in player_source_inputs:
            source_url = self._clean_text(row.get('source_url'))
            if not player_id or not source_url:
                continue

            evidence = self._clean_text(row.get('evidence'))
            source_key = (player_id, source_url, evidence or '')
            if source_key in seen_player_source_keys or source_key in existing_player_source_keys:
                duplicates += 1
                continue
            seen_player_source_keys.add(source_key)

            player_source_records.append({
                'player_id': player_id,
                'crawled_article_id': crawled_id_map.get(source_url),
                'source_url': source_url,
                'source_title': self._clean_text(row.get('source_title')),
                'published_at': SupabaseCrawledArticleStore._format_published_at(row.get('published_at') or ''),
                'source': self._clean_text(row.get('source')),
                'category': self._clean_text(row.get('article_category') or row.get('category')),
                'evidence': evidence,
                'confidence': self._to_confidence(row.get('confidence')),
                'extracted_raw': row.get('extracted_raw') or row,
            })

        player_sources_inserted = 0
        try:
            if player_source_records:
                response = self.supabase.table('player_article_sources').insert(player_source_records).execute()
                player_sources_inserted = len(response.data or player_source_records)
                print(f"[DB] player_article_sources 保存完了: {player_sources_inserted}件")
        except Exception as e:
            print(f"[DB] player_article_sources 保存エラー: {e}")
            return {
                'total': len(rows),
                'inserted': inserted,
                'sources_inserted': sources_inserted,
                'player_sources_inserted': 0,
                'linked_existing_players': linked_existing_players,
                'skipped_existing_players': linked_existing_players,
                'duplicates': duplicates,
                'errors': len(player_source_records),
            }

        return {
            'total': len(rows),
            'inserted': inserted,
            'sources_inserted': sources_inserted,
            'player_sources_inserted': player_sources_inserted,
            'linked_existing_players': linked_existing_players,
            'skipped_existing_players': linked_existing_players,
            'duplicates': duplicates,
            'errors': 0,
        }

    def _refresh_candidate_source_summaries(self, candidate_ids: List[str]) -> None:
        if self.dummy_mode or self.supabase is None or not candidate_ids:
            return

        for candidate_id in candidate_ids:
            try:
                response = (
                    self.supabase
                    .table('player_candidate_sources')
                    .select('source_url,source_title,evidence,confidence,created_at')
                    .eq('player_candidate_id', candidate_id)
                    .order('created_at', desc=True)
                    .execute()
                )
                sources = response.data or []
                latest = sources[0] if sources else {}
                self.supabase.table('player_candidates').update({
                    'source_count': len(sources),
                    'latest_source_url': latest.get('source_url'),
                    'latest_source_title': latest.get('source_title'),
                    'latest_evidence': latest.get('evidence'),
                    'latest_confidence': latest.get('confidence'),
                }).eq('id', candidate_id).execute()
            except Exception as e:
                print(f"[DB] player_candidates source_count更新エラー: {candidate_id}: {e}")

class SupabaseAttentionSignalStore:
    """attention_signals への注目度シグナル保存。"""

    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode, self.supabase = _init_supabase_client(dummy_mode=dummy_mode)
        if not self.dummy_mode:
            print("✅ Supabaseクライアントを初期化しました（attention_signals）")

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ('true', '1', 'yes', 'y')

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _format_published_at(date_value: Any) -> Optional[str]:
        return SupabaseCrawledArticleStore._format_published_at(str(date_value or ''))

    def _get_existing_keys(self, source_urls: List[str]) -> Set[Tuple[str, str]]:
        if self.dummy_mode or self.supabase is None or not source_urls:
            return set()

        try:
            response = (
                self.supabase
                .table('attention_signals')
                .select('source_url,evidence_hash')
                .in_('source_url', sorted(set(source_urls)))
                .execute()
            )
            return {
                (row.get('source_url') or '', row.get('evidence_hash') or '')
                for row in (response.data or [])
            }
        except Exception as e:
            print(f"[DB] attention_signals 既存取得エラー: {e}")
            return set()

    def _get_player_links_by_source_urls(self, source_urls: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
        if self.dummy_mode or self.supabase is None or not source_urls:
            return {}

        links: Dict[str, Dict[str, Optional[str]]] = {}
        unique_urls = sorted(set(source_urls))

        try:
            response = (
                self.supabase
                .table('player_article_sources')
                .select('source_url,player_id')
                .in_('source_url', unique_urls)
                .execute()
            )
            for row in response.data or []:
                source_url = row.get('source_url')
                player_id = row.get('player_id')
                if source_url and player_id and source_url not in links:
                    links[source_url] = {
                        'player_id': player_id,
                        'player_candidate_id': None,
                        'player_name': None,
                    }
        except Exception as e:
            print(f"[DB] player_article_sources 紐付け取得エラー: {e}")

        try:
            response = (
                self.supabase
                .table('player_candidate_sources')
                .select('source_url,player_candidate_id')
                .in_('source_url', unique_urls)
                .execute()
            )
            candidate_ids = sorted({
                row.get('player_candidate_id')
                for row in (response.data or [])
                if row.get('player_candidate_id')
            })
            candidate_name_map: Dict[str, str] = {}
            if candidate_ids:
                candidate_response = (
                    self.supabase
                    .table('player_candidates')
                    .select('id,name,player_id')
                    .in_('id', candidate_ids)
                    .execute()
                )
                for candidate in candidate_response.data or []:
                    if candidate.get('id'):
                        candidate_name_map[candidate['id']] = candidate.get('name') or ''

            for row in response.data or []:
                source_url = row.get('source_url')
                candidate_id = row.get('player_candidate_id')
                if source_url and candidate_id and source_url not in links:
                    links[source_url] = {
                        'player_id': None,
                        'player_candidate_id': candidate_id,
                        'player_name': candidate_name_map.get(candidate_id),
                    }
        except Exception as e:
            print(f"[DB] player_candidate_sources 紐付け取得エラー: {e}")

        return links

    def insert_attention_signals(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        rows = []
        for article in articles:
            rows.extend(article.get('attention_rows', []))

        if not rows:
            return {'total': 0, 'inserted': 0, 'duplicates': 0, 'errors': 0}

        if self.dummy_mode or self.supabase is None:
            print(f"[DB] attention_signals 保存スキップ（ダミーモード）: {len(rows)}件")
            return {'total': len(rows), 'inserted': 0, 'duplicates': 0, 'errors': 0}

        source_urls = [row[4] for row in rows if len(row) > 4 and row[4]]
        crawled_id_map = SupabaseCrawledArticleStore(dummy_mode=False).get_article_id_map_by_urls(source_urls)
        existing_keys = self._get_existing_keys(source_urls)
        player_link_map = self._get_player_links_by_source_urls(source_urls)

        records = []
        seen_keys: Set[Tuple[str, str]] = set()
        duplicates = 0

        for row in rows:
            if len(row) < 12:
                continue

            source_url = str(row[4] or '').strip()
            evidence = str(row[11] or '').strip()
            if not source_url or not evidence:
                continue

            evidence_hash = hashlib.md5(evidence.encode('utf-8')).hexdigest()
            key = (source_url, evidence_hash)
            if key in seen_keys or key in existing_keys:
                duplicates += 1
                continue
            seen_keys.add(key)

            team_keys = [team_key.strip() for team_key in str(row[7] or '').split(',') if team_key.strip()]
            player_link = player_link_map.get(source_url, {})
            records.append({
                'crawled_article_id': crawled_id_map.get(source_url),
                'player_id': player_link.get('player_id'),
                'player_candidate_id': player_link.get('player_candidate_id'),
                'player_name': player_link.get('player_name'),
                'source_url': source_url,
                'source_title': str(row[3] or '').strip() or None,
                'published_at': self._format_published_at(row[0]),
                'source': str(row[1] or '').strip() or None,
                'category': str(row[2] or '').strip() or None,
                'team_count': self._to_int(row[5]),
                'person_count': self._to_int(row[6]),
                'team_keys': team_keys,
                'has_npb': self._to_bool(row[8]),
                'has_mlb': self._to_bool(row[9]),
                'score': self._to_int(row[10]),
                'evidence': evidence,
            })

        if not records:
            return {'total': len(rows), 'inserted': 0, 'duplicates': duplicates, 'errors': 0}

        try:
            response = self.supabase.table('attention_signals').insert(records).execute()
            inserted = len(response.data or records)
            print(f"[DB] attention_signals 保存完了: {inserted}件")
            return {'total': len(rows), 'inserted': inserted, 'duplicates': duplicates, 'errors': 0}
        except Exception as e:
            print(f"[DB] attention_signals 保存エラー: {e}")
            return {'total': len(rows), 'inserted': 0, 'duplicates': duplicates, 'errors': len(records)}


class SupabaseScoutVisitStore:
    """scout_visits への視察情報保存(球団 x 選手単位で正規化)。"""

    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode, self.supabase = _init_supabase_client(dummy_mode=dummy_mode)
        if not self.dummy_mode:
            print("✅ Supabaseクライアントを初期化しました(scout_visits)")

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        try:
            if value is None or value == '':
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_optional_str(value: Any) -> Optional[str]:
        text = str(value or '').strip()
        return text or None

    @staticmethod
    def _format_published_at(date_value: Any) -> Optional[str]:
        return SupabaseCrawledArticleStore._format_published_at(str(date_value or ''))

    def _get_existing_keys(self, source_urls: List[str]) -> Set[Tuple[str, str, str, str]]:
        if self.dummy_mode or self.supabase is None or not source_urls:
            return set()

        try:
            response = (
                self.supabase
                .table('scout_visits')
                .select('source_url,evidence_hash,team_key,player_name')
                .in_('source_url', sorted(set(source_urls)))
                .execute()
            )
            return {
                (
                    row.get('source_url') or '',
                    row.get('evidence_hash') or '',
                    row.get('team_key') or '',
                    row.get('player_name') or '',
                )
                for row in (response.data or [])
            }
        except Exception as e:
            print(f"[DB] scout_visits 既存取得エラー: {e}")
            return set()

    def insert_scout_visits(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        rows = []
        for article in articles:
            rows.extend(article.get('scout_visit_rows', []))

        if not rows:
            return {'total': 0, 'inserted': 0, 'duplicates': 0, 'errors': 0}

        if self.dummy_mode or self.supabase is None:
            print(f"[DB] scout_visits 保存スキップ(ダミーモード): {len(rows)}件")
            return {'total': len(rows), 'inserted': 0, 'duplicates': 0, 'errors': 0}

        source_urls = [row.get('source_url') for row in rows if row.get('source_url')]
        crawled_id_map = SupabaseCrawledArticleStore(dummy_mode=False).get_article_id_map_by_urls(source_urls)
        existing_keys = self._get_existing_keys(source_urls)
        attention_store = SupabaseAttentionSignalStore(dummy_mode=False)
        player_link_map = attention_store._get_player_links_by_source_urls(source_urls)

        records = []
        seen_keys: Set[Tuple[str, str, str, str]] = set()
        duplicates = 0

        for row in rows:
            source_url = self._to_optional_str(row.get('source_url'))
            evidence = self._to_optional_str(row.get('evidence'))
            if not source_url or not evidence:
                continue

            team_key = self._to_optional_str(row.get('team_key'))
            player_name = self._to_optional_str(row.get('player_name'))
            evidence_hash = hashlib.md5(evidence.encode('utf-8')).hexdigest()
            key = (source_url, evidence_hash, team_key or '', player_name or '')
            if key in seen_keys or key in existing_keys:
                duplicates += 1
                continue
            seen_keys.add(key)

            player_link = player_link_map.get(source_url, {})
            records.append({
                'crawled_article_id': crawled_id_map.get(source_url),
                'player_id': player_link.get('player_id'),
                'player_candidate_id': player_link.get('player_candidate_id'),
                'player_name': player_link.get('player_name') or player_name,
                'team_key': team_key,
                'person_count': self._to_int(row.get('person_count')),
                'event_date': self._to_optional_str(row.get('event_date')),
                'event_date_text': self._to_optional_str(row.get('event_date_text')),
                'event_date_precision': self._to_optional_str(row.get('event_date_precision')),
                'source_url': source_url,
                'source_title': self._to_optional_str(row.get('source_title')),
                'published_at': self._format_published_at(row.get('published_at')),
                'source': self._to_optional_str(row.get('source')),
                'category': self._to_optional_str(row.get('article_category')),
                'evidence': evidence,
            })

        if not records:
            return {'total': len(rows), 'inserted': 0, 'duplicates': duplicates, 'errors': 0}

        try:
            response = self.supabase.table('scout_visits').insert(records).execute()
            inserted = len(response.data or records)
            print(f"[DB] scout_visits 保存完了: {inserted}件")
            return {'total': len(rows), 'inserted': inserted, 'duplicates': duplicates, 'errors': 0}
        except Exception as e:
            print(f"[DB] scout_visits 保存エラー: {e}")
            return {'total': len(rows), 'inserted': 0, 'duplicates': duplicates, 'errors': len(records)}


class SupabaseDraftWatchCandidateStore:
    """
    draft_watch_article_candidates / draft_watch_article_candidate_sources への
    Draft-Watch記事候補の保存・トピック判定・下書き生成（Phase 4）。

    1日1回の朝バッチから呼び出され、前回バッチ以降に増えた attention_signals を起点に
    トピック判定（topic_key一致 → ルールベース近傍判定）でトピックへ合流させるか新規作成し、
    summary_json / importance_score を更新したうえで、閾値を超えた候補だけ下書きをAI生成する。
    """

    DEFAULT_LOOKBACK_HOURS = 30
    GENERATION_THRESHOLD = 1
    NEAR_MATCH_DAYS = 3

    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode, self.supabase = _init_supabase_client(dummy_mode=dummy_mode)
        if not self.dummy_mode:
            print("✅ Supabaseクライアントを初期化しました（draft_watch_article_candidates）")

    @staticmethod
    def _to_optional_str(value: Any) -> Optional[str]:
        text = str(value or '').strip()
        return text or None

    @staticmethod
    def _to_int_or_zero(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _parse_event_date(value: Optional[str]):
        if not value:
            return None
        try:
            return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def get_cutoff_iso(self) -> str:
        """
        「それまでに溜まった記事」の起点時刻を決める。
        前回バッチが作成した出典の最終時刻を起点にし、まだ候補が無ければ DEFAULT_LOOKBACK_HOURS 時間前を使う。
        """
        fallback = (now_jst() - timedelta(hours=self.DEFAULT_LOOKBACK_HOURS)).isoformat()
        if self.dummy_mode or self.supabase is None:
            return fallback
        try:
            response = (
                self.supabase
                .table('draft_watch_article_candidate_sources')
                .select('created_at')
                .order('created_at', desc=True)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            if rows and rows[0].get('created_at'):
                return rows[0]['created_at']
        except Exception as e:
            print(f"[DB] draft_watch_article_candidate_sources cutoff取得エラー: {e}")
        return fallback

    def fetch_attention_signals_since(self, cutoff_iso: str) -> List[Dict[str, Any]]:
        if self.dummy_mode or self.supabase is None:
            return []
        try:
            response = (
                self.supabase
                .table('attention_signals')
                .select('*')
                .gt('created_at', cutoff_iso)
                .order('created_at')
                .execute()
            )
            return response.data or []
        except Exception as e:
            print(f"[DB] attention_signals 取得エラー: {e}")
            return []

    def fetch_player_info(self, player_ids: List[str], player_candidate_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """`player:{id}` / `candidate:{id}` -> {'name','team','positions','draft_year'} のマップを返す。"""
        info: Dict[str, Dict[str, Any]] = {}
        if self.dummy_mode or self.supabase is None:
            return info

        unique_player_ids = sorted({pid for pid in player_ids if pid})
        if unique_player_ids:
            try:
                response = (
                    self.supabase
                    .table('players')
                    .select('id,name,team,position,draft_year')
                    .in_('id', unique_player_ids)
                    .execute()
                )
                for row in response.data or []:
                    if row.get('id'):
                        info[f"player:{row['id']}"] = row
            except Exception as e:
                print(f"[DB] players 取得エラー: {e}")

        unique_candidate_ids = sorted({cid for cid in player_candidate_ids if cid})
        if unique_candidate_ids:
            try:
                response = (
                    self.supabase
                    .table('player_candidates')
                    .select('id,name,team,position,draft_year')
                    .in_('id', unique_candidate_ids)
                    .execute()
                )
                for row in response.data or []:
                    if row.get('id'):
                        info[f"candidate:{row['id']}"] = row
            except Exception as e:
                print(f"[DB] player_candidates 取得エラー: {e}")

        return info

    def fetch_scout_visits_for_urls(self, source_urls: List[str]) -> List[Dict[str, Any]]:
        if self.dummy_mode or self.supabase is None or not source_urls:
            return []
        try:
            response = (
                self.supabase
                .table('scout_visits')
                .select('source_url,team_key,player_name,event_date,event_date_text,evidence')
                .in_('source_url', sorted(set(source_urls)))
                .execute()
            )
            return response.data or []
        except Exception as e:
            print(f"[DB] scout_visits 取得エラー: {e}")
            return []

    def fetch_scout_comments_for_urls(self, source_urls: List[str]) -> List[Dict[str, Any]]:
        if self.dummy_mode or self.supabase is None or not source_urls:
            return []
        try:
            response = (
                self.supabase
                .table('scout_comments')
                .select('source_url,team_name,scout_name,comment,player_name')
                .in_('source_url', sorted(set(source_urls)))
                .execute()
            )
            return response.data or []
        except Exception as e:
            print(f"[DB] scout_comments 取得エラー: {e}")
            return []

    def _resolve_event_date(self, source_url: str, player_name: Optional[str], published_at: Any) -> Tuple[Optional[str], Optional[str]]:
        """
        トピックの「出来事の日付」を決める。scout_visitsに推定日があればそれを優先し、
        なければ記事の公開日（published_atの日付部分）を使う。
        """
        if player_name:
            visits = self.fetch_scout_visits_for_urls([source_url])
            for visit in visits:
                if visit.get('player_name') == player_name and visit.get('event_date'):
                    return visit['event_date'], visit.get('event_date_text')

        if published_at:
            return str(published_at)[:10], None
        return None, None

    def find_candidate_by_topic_key(self, topic_key: Optional[str]) -> Optional[Dict[str, Any]]:
        if self.dummy_mode or self.supabase is None or not topic_key:
            return None
        try:
            response = (
                self.supabase
                .table('draft_watch_article_candidates')
                .select('*')
                .eq('topic_key', topic_key)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            return rows[0] if rows else None
        except Exception as e:
            print(f"[DB] draft_watch_article_candidates topic_key検索エラー: {e}")
            return None

    def find_candidate_by_rule(
        self,
        topic_type: str,
        main_player_id: Optional[str],
        main_player_name: Optional[str],
        event_date: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        topic_keyの完全一致で見つからない場合の近傍判定。
        同じtopic_typeかつ主役選手が一致する候補のうち、出来事の日付が前後 NEAR_MATCH_DAYS 日以内のものを合流先とする。
        """
        if self.dummy_mode or self.supabase is None:
            return None
        if not (main_player_id or main_player_name):
            return None

        try:
            query = (
                self.supabase
                .table('draft_watch_article_candidates')
                .select('*')
                .eq('topic_type', topic_type)
                .in_('status', ['draft', 'reviewed'])
                .order('created_at', desc=True)
                .limit(20)
            )
            if main_player_id:
                query = query.eq('main_player_id', main_player_id)
            elif main_player_name:
                query = query.eq('main_player_name', main_player_name)
            candidates = query.execute().data or []
        except Exception as e:
            print(f"[DB] draft_watch_article_candidates 近傍検索エラー: {e}")
            return None

        target_date = self._parse_event_date(event_date)
        if target_date is None:
            return candidates[0] if candidates else None

        for candidate in candidates:
            for event in (candidate.get('summary_json') or {}).get('events') or []:
                candidate_date = self._parse_event_date(event.get('date'))
                if candidate_date and abs((candidate_date - target_date).days) <= self.NEAR_MATCH_DAYS:
                    return candidate
        return None

    def get_sources(self, candidate_id: str) -> List[Dict[str, Any]]:
        if self.dummy_mode or self.supabase is None:
            return []
        try:
            response = (
                self.supabase
                .table('draft_watch_article_candidate_sources')
                .select('*')
                .eq('draft_watch_article_candidate_id', candidate_id)
                .order('created_at')
                .execute()
            )
            return response.data or []
        except Exception as e:
            print(f"[DB] draft_watch_article_candidate_sources 取得エラー: {e}")
            return []

    def add_source(self, candidate_id: str, crawled_article_id: Optional[str], source_url: str, role: str) -> bool:
        if self.dummy_mode or self.supabase is None:
            return False
        try:
            self.supabase.table('draft_watch_article_candidate_sources').insert({
                'draft_watch_article_candidate_id': candidate_id,
                'crawled_article_id': crawled_article_id,
                'source_url': source_url,
                'role': role,
            }).execute()
            return True
        except Exception as e:
            # 既に同じ (candidate_id, source_url) が登録済み（unique制約）の場合もここに来る
            print(f"[DB] draft_watch_article_candidate_sources 追加スキップ: {e}")
            return False

    def insert_candidate(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.dummy_mode or self.supabase is None:
            return None
        try:
            response = self.supabase.table('draft_watch_article_candidates').insert(record).execute()
            rows = response.data or []
            return rows[0] if rows else None
        except Exception as e:
            print(f"[DB] draft_watch_article_candidates 作成エラー: {e}")
            return None

    def update_candidate(self, candidate_id: str, fields: Dict[str, Any]) -> bool:
        if self.dummy_mode or self.supabase is None:
            return False
        try:
            self.supabase.table('draft_watch_article_candidates').update(fields).eq('id', candidate_id).execute()
            return True
        except Exception as e:
            print(f"[DB] draft_watch_article_candidates 更新エラー: {e}")
            return False

    @staticmethod
    def _build_placeholder_title(topic_type: str, main_player_name: Optional[str], signal: Dict[str, Any]) -> str:
        """新規トピック作成時点のタイトル。下書きAI生成時にAIが付けたタイトルへ置き換えられる。"""
        if topic_type == 'player_watch' and main_player_name:
            team_count = signal.get('team_count') or 0
            person_count = signal.get('person_count') or 0
            if team_count or person_count:
                return f"{main_player_name}にスカウト視察集中（{team_count}球団{person_count}人）"
            return f"{main_player_name}にスカウトの注目集まる"
        if topic_type == 'scout_meeting':
            return "スカウト会議・編成動向まとめ"
        return signal.get('source_title') or "ドラフト関連トピック"

    def process_new_signals(self) -> Dict[str, int]:
        """前回バッチ以降の attention_signals を起点に、トピック判定・候補更新・下書き生成を行う。"""
        stats = {'signals': 0, 'candidates_created': 0, 'candidates_updated': 0, 'drafts_generated': 0, 'errors': 0}

        if self.dummy_mode or self.supabase is None:
            print("[DB] draft_watch_article_candidates 処理スキップ（ダミーモード）")
            return stats

        cutoff_iso = self.get_cutoff_iso()
        signals = self.fetch_attention_signals_since(cutoff_iso)
        stats['signals'] = len(signals)
        if not signals:
            print(f"[DraftWatch] 新着シグナルなし（基準時刻: {cutoff_iso}）")
            return stats

        print(f"[DraftWatch] 新着 attention_signals: {len(signals)}件（基準時刻: {cutoff_iso}）")

        player_ids = [s.get('player_id') for s in signals if s.get('player_id')]
        candidate_ids = [s.get('player_candidate_id') for s in signals if s.get('player_candidate_id')]
        player_info = self.fetch_player_info(player_ids, candidate_ids)

        source_urls_all = [s.get('source_url') for s in signals if s.get('source_url')]
        crawled_id_map = SupabaseCrawledArticleStore(dummy_mode=False).get_article_id_map_by_urls(source_urls_all)

        for signal in signals:
            try:
                self._process_single_signal(signal, player_info, crawled_id_map, stats)
            except Exception as e:
                print(f"[DraftWatch] シグナル処理エラー: {e}")
                stats['errors'] += 1

        return stats

    def regenerate_all_drafts(self, only_missing: bool = False) -> Dict[str, int]:
        """
        既存の候補について summary_json / importance_score / 下書き本文を作り直す。
        新着シグナルの有無に関係なく走るので、プロンプト改善を既存候補へ反映する用途に使う。
        only_missing=True のときは本文（draft_article_markdown）が未生成の候補だけを対象にする。
        status=draft（人間レビュー前）の候補のみ対象。
        """
        stats = {'signals': 0, 'candidates_created': 0, 'candidates_updated': 0, 'drafts_generated': 0, 'errors': 0}

        if self.dummy_mode or self.supabase is None:
            print("[DB] draft_watch_article_candidates 再生成スキップ（ダミーモード）")
            return stats

        try:
            rows = (self.supabase.table('draft_watch_article_candidates').select('*').execute()).data or []
        except Exception as e:
            print(f"[DB] 候補一覧取得エラー: {e}")
            return stats

        targets = []
        for r in rows:
            if r.get('status') != 'draft':
                continue
            if only_missing and r.get('draft_article_markdown'):
                continue
            targets.append(r)

        print(f"[DraftWatch] 再生成対象: {len(targets)}件（only_missing={only_missing}）")

        for candidate in targets:
            try:
                summary = candidate.get('summary_json') or {}
                if isinstance(summary, str):
                    summary = json.loads(summary)
                main_player = summary.get('main_player') or {}
                topic_type = summary.get('topic_type') or candidate.get('topic_type') or 'other'
                main_player_name = candidate.get('main_player_name') or main_player.get('name')
                main_player_team = main_player.get('team')
                main_player_positions = main_player.get('positions') or main_player.get('position') or []
                self._refresh_summary_and_score(
                    candidate, topic_type, main_player_name, main_player_team, main_player_positions, stats
                )
                stats['candidates_updated'] += 1
            except Exception as e:
                print(f"[DraftWatch] 再生成エラー id={candidate.get('id')}: {e}")
                stats['errors'] += 1

        return stats

    def _process_single_signal(
        self,
        signal: Dict[str, Any],
        player_info: Dict[str, Dict[str, Any]],
        crawled_id_map: Dict[str, str],
        stats: Dict[str, int],
    ) -> None:
        from utils import normalize_player_key, build_topic_key, has_scout_meeting_signal

        source_url = self._to_optional_str(signal.get('source_url'))
        if not source_url:
            return

        evidence = self._to_optional_str(signal.get('evidence')) or ''
        source_title = self._to_optional_str(signal.get('source_title'))
        published_at = signal.get('published_at')

        player_id = signal.get('player_id')
        player_candidate_id = signal.get('player_candidate_id')
        info = None
        if player_id:
            info = player_info.get(f"player:{player_id}")
        elif player_candidate_id:
            info = player_info.get(f"candidate:{player_candidate_id}")

        main_player_name = self._to_optional_str(signal.get('player_name')) or (info.get('name') if info else None)
        main_player_team = (info or {}).get('team')
        main_player_positions = (info or {}).get('position') or []
        draft_year = (info or {}).get('draft_year')

        # トピック種別の判定（主役選手が分かれば player_watch、スカウト会議系の検出語があれば scout_meeting、それ以外は other）
        if main_player_name:
            topic_type = 'player_watch'
        elif has_scout_meeting_signal(f"{source_title or ''}\n{evidence}"):
            topic_type = 'scout_meeting'
        else:
            topic_type = 'other'

        event_date, _event_date_text = self._resolve_event_date(source_url, main_player_name, published_at)

        topic_key = None
        if topic_type == 'player_watch':
            topic_key = build_topic_key(
                'player_watch',
                draft_year=draft_year,
                player_key=normalize_player_key(main_player_name),
                event_date=event_date,
            )
        elif topic_type == 'scout_meeting':
            team_keys = signal.get('team_keys') or []
            topic_key = build_topic_key(
                'scout_meeting',
                team=(team_keys[0] if team_keys else None),
                meeting_date=event_date,
                draft_year=draft_year,
            )

        if not topic_key:
            normalized_title = re.sub(r'\s+', '', source_title or evidence)
            title_hash = hashlib.md5(normalized_title.encode('utf-8')).hexdigest()
            topic_key = build_topic_key('other', title_hash=title_hash)
            topic_type = 'other'

        candidate = self.find_candidate_by_topic_key(topic_key)
        if not candidate:
            candidate = self.find_candidate_by_rule(topic_type, player_id, main_player_name, event_date)

        crawled_article_id = crawled_id_map.get(source_url)

        if candidate is None:
            record = {
                'topic_key': topic_key,
                'topic_type': topic_type,
                'main_player_id': player_id,
                'main_player_name': main_player_name,
                'title': self._build_placeholder_title(topic_type, main_player_name, signal),
                'importance_score': 0,
                'source_urls': [source_url],
                'status': 'draft',
            }
            candidate = self.insert_candidate(record)
            if not candidate:
                stats['errors'] += 1
                return
            self.add_source(candidate['id'], crawled_article_id, source_url, role='primary')
            stats['candidates_created'] += 1
            print(f"[DraftWatch] 新規トピック作成: {topic_key} ({record['title']})")
        else:
            if source_url in (candidate.get('source_urls') or []):
                return
            if not self.add_source(candidate['id'], crawled_article_id, source_url, role='source'):
                return
            source_urls = list(dict.fromkeys((candidate.get('source_urls') or []) + [source_url]))
            self.update_candidate(candidate['id'], {'source_urls': source_urls})
            candidate['source_urls'] = source_urls
            stats['candidates_updated'] += 1
            print(f"[DraftWatch] 既存トピックへ合流: {candidate.get('topic_key')} <- {source_url}")

        self._refresh_summary_and_score(
            candidate, topic_type, main_player_name, main_player_team, main_player_positions, stats
        )

    def _refresh_summary_and_score(
        self,
        candidate: Dict[str, Any],
        topic_type: str,
        main_player_name: Optional[str],
        main_player_team: Optional[str],
        main_player_positions: List[str],
        stats: Dict[str, int],
    ) -> None:
        """
        候補に紐づく全ソースの情報からsummary_jsonを作り直し、importance_scoreを再計算する。
        importance_scoreが閾値を超え、かつまだ人間レビュー前（status=draft）なら下書きをAI生成（再生成含む）する。
        """
        candidate_id = candidate['id']
        sources = self.get_sources(candidate_id)
        source_urls = [s.get('source_url') for s in sources if s.get('source_url')]
        if not source_urls:
            return

        try:
            related_signals = (
                self.supabase
                .table('attention_signals')
                .select('*')
                .in_('source_url', source_urls)
                .execute()
            ).data or []
        except Exception as e:
            print(f"[DB] attention_signals 関連取得エラー: {e}")
            related_signals = []

        scout_visits = self.fetch_scout_visits_for_urls(source_urls)
        scout_comments = self.fetch_scout_comments_for_urls(source_urls)

        team_count = max((self._to_int_or_zero(s.get('team_count')) for s in related_signals), default=0)
        person_count = max((self._to_int_or_zero(s.get('person_count')) for s in related_signals), default=0)
        has_mlb = any(bool(s.get('has_mlb')) for s in related_signals)
        team_keys = sorted(
            {key for s in related_signals for key in (s.get('team_keys') or [])}
            | {v.get('team_key') for v in scout_visits if v.get('team_key')}
        )

        meta_by_url: Dict[str, Dict[str, Optional[str]]] = {}
        events = []
        seen_event_keys: Set[Tuple[Optional[str], str]] = set()
        for s in related_signals:
            url = s.get('source_url')
            if url and url not in meta_by_url:
                meta_by_url[url] = {'title': s.get('source_title'), 'source': s.get('source')}
            date = str(s.get('published_at'))[:10] if s.get('published_at') else None
            summary = self._to_optional_str(s.get('evidence'))
            if not summary:
                continue
            key = (date, summary)
            if key in seen_event_keys:
                continue
            seen_event_keys.add(key)
            events.append({'date': date, 'summary': summary})
        events.sort(key=lambda e: e.get('date') or '')

        scout_comment_entries = [
            {'team': c.get('team_name'), 'scout_name': c.get('scout_name'), 'comment': c.get('comment')}
            for c in scout_comments
        ]

        source_entries = []
        for s in sources:
            url = s.get('source_url')
            meta = meta_by_url.get(url, {})
            source_entries.append({
                'url': url,
                'title': meta.get('title'),
                'source': meta.get('source'),
                'role': s.get('role'),
            })

        summary_json = {
            'topic_type': topic_type,
            'topic_key': candidate.get('topic_key'),
            'main_player': (
                {'name': main_player_name, 'team': main_player_team, 'positions': main_player_positions}
                if main_player_name else None
            ),
            'attention': {
                'team_count': team_count,
                'person_count': person_count,
                'teams': team_keys,
                'has_mlb': has_mlb,
            },
            'scout_comments': scout_comment_entries,
            'events': events,
            'sources': source_entries,
            'warnings': [],
        }

        base_score = max((self._to_int_or_zero(s.get('score')) for s in related_signals), default=0)
        multi_source_bonus = min(max(len(source_urls) - 1, 0), 3)
        meeting_bonus = 2 if topic_type == 'scout_meeting' else 0
        importance_score = base_score + multi_source_bonus + meeting_bonus

        update_fields: Dict[str, Any] = {
            'summary_json': summary_json,
            'importance_score': importance_score,
        }

        if importance_score >= self.GENERATION_THRESHOLD and candidate.get('status') == 'draft':
            from ai.gemini import generate_draft_watch_article_with_gemini
            generated = generate_draft_watch_article_with_gemini(summary_json)
            if generated:
                update_fields['draft_article_markdown'] = generated['markdown']
                update_fields['title'] = generated['title']
                stats['drafts_generated'] += 1
                print(f"[DraftWatch] 下書き生成: {generated['title']}（importance_score={importance_score}）")

        self.update_candidate(candidate_id, update_fields)


class SupabaseScoutCommentInserter:
    """Supabaseにスカウトコメントを直接INSERTする機能"""
    
    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode = dummy_mode or not SUPABASE_AVAILABLE
        self.player_lookup = SupabasePlayerLookup(dummy_mode=dummy_mode)
        
        if not self.dummy_mode:
            self.supabase_url = os.getenv('SUPABASE_URL')
            # サービスロールキーを優先、なければ通常のキーを使用
            self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
            
            if not self.supabase_url or not self.supabase_key:
                print("⚠️  Supabase環境変数が設定されていません。ダミーモードで動作します。")
                self.dummy_mode = True
            else:
                try:
                    self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
                    print("✅ Supabaseクライアントを初期化しました（INSERT機能）")
                except Exception as e:
                    print(f"⚠️  Supabase接続エラー: {e}")
                    print("ダミーモードで動作します。")
                    self.dummy_mode = True
    
    def check_duplicate_comment(self, comment: str, scout_name: str, team_name: str) -> bool:
        """重複コメントをチェック"""
        if self.dummy_mode:
            # ダミーモードでは重複チェックをスキップ
            return False
        
        try:
            # 同じコメント内容、スカウト名、球団名の組み合わせをチェック
            response = self.supabase.table('scout_comments').select('id').eq('comment', comment).eq('scout_name', scout_name).eq('team_name', team_name).limit(1).execute()
            
            if response.data:
                print(f"[重複検出] スカウト: {scout_name}, 球団: {team_name}")
                return True
            
            return False
            
        except Exception as e:
            print(f"[重複チェックエラー] {e}")
            return False  # エラーの場合は重複としない

    def lookup_candidate_ids(self, scout_rows: List[List[str]]) -> Dict[Tuple[str, str], str]:
        """(player_name, source_url) から player_candidate_id を取得"""
        if self.dummy_mode or not scout_rows:
            return {}

        source_urls = sorted({
            row[6].strip()
            for row in scout_rows
            if len(row) >= 7 and row[6].strip()
        })
        if not source_urls:
            return {}

        try:
            response = (
                self.supabase
                .table('player_candidate_sources')
                .select('source_url,player_candidate_id')
                .in_('source_url', source_urls)
                .execute()
            )
            candidate_ids = sorted({
                row.get('player_candidate_id')
                for row in (response.data or [])
                if row.get('player_candidate_id')
            })
            candidate_name_map: Dict[str, str] = {}
            if candidate_ids:
                candidate_response = (
                    self.supabase
                    .table('player_candidates')
                    .select('id,name')
                    .in_('id', candidate_ids)
                    .execute()
                )
                candidate_name_map = {
                    row['id']: self.player_lookup.normalize_name(row.get('name') or '')
                    for row in (candidate_response.data or [])
                    if row.get('id')
                }
        except Exception as e:
            print(f"[DB] scout_comments 候補紐付け取得エラー: {e}")
            return {}

        candidate_map: Dict[Tuple[str, str], str] = {}
        for row in response.data or []:
            source_url = (row.get('source_url') or '').strip()
            candidate_id = row.get('player_candidate_id')
            player_name = candidate_name_map.get(candidate_id or '')
            if player_name and source_url and candidate_id:
                candidate_map[(player_name, source_url)] = candidate_id

        return candidate_map
    
    def insert_scout_comment(self, scout_data: Dict[str, str]) -> bool:
        """単一のスカウトコメントをINSERT"""
        if self.dummy_mode:
            print(f"[ダミーモード] スカウトコメントINSERT: {scout_data.get('player_name', 'Unknown')}")
            return True
        
        try:
            # 重複チェック
            if self.check_duplicate_comment(
                scout_data['comment'], 
                scout_data['scout_name'], 
                scout_data['team_name']
            ):
                return False  # 重複の場合はINSERTしない
            
            # INSERT実行
            insert_data = {
                'player_id': scout_data.get('player_id'),
                'player_candidate_id': scout_data.get('player_candidate_id'),
                'player_name': scout_data.get('player_name'),
                'team_name': scout_data['team_name'],
                'scout_name': scout_data['scout_name'],
                'comment': scout_data['comment'],
                'published_at': scout_data.get('published_at'),
                'source_url': scout_data.get('source_url')
            }
            
            response = self.supabase.table('scout_comments').insert(insert_data).execute()
            
            if response.data:
                print(f"[INSERT成功] 選手: {scout_data.get('player_name', 'Unknown')}, スカウト: {scout_data['scout_name']}")
                return True
            else:
                print(f"[INSERT失敗] 選手: {scout_data.get('player_name', 'Unknown')}")
                return False
                
        except Exception as e:
            print(f"[INSERTエラー] {scout_data.get('player_name', 'Unknown')}: {e}")
            return False
    
    def insert_multiple_scout_comments(self, scout_rows: List[List[str]]) -> Dict[str, int]:
        """複数のスカウトコメントを一括INSERT"""
        if not scout_rows:
            return {"total": 0, "inserted": 0, "duplicates": 0, "errors": 0}
        
        # 選手名を抽出して選手IDを一括取得
        player_names = [row[0] for row in scout_rows if len(row) > 0]
        player_id_map = self.player_lookup.lookup_multiple_players(player_names)
        candidate_id_map = self.lookup_candidate_ids(scout_rows)
        
        results = {"total": len(scout_rows), "inserted": 0, "duplicates": 0, "errors": 0}
        
        mode_text = "ダミーモード" if self.dummy_mode else "Supabase"
        print(f"[{mode_text}] {len(scout_rows)}件のスカウトコメントをINSERT中...")
        
        for i, row in enumerate(scout_rows, 1):
            if len(row) < 7:
                results["errors"] += 1
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
            normalized_player_name = self.player_lookup.normalize_name(player_name)
            player_candidate_id = None
            if player_id is None:
                player_candidate_id = candidate_id_map.get((normalized_player_name, article_url.strip()))
            
            # データを正規化
            scout_data = {
                'player_id': player_id,
                'player_candidate_id': player_candidate_id,
                'player_name': player_name,
                'team_name': scout_team.strip(),
                'scout_name': scout_name.strip(),
                'comment': comment_content.strip(),
                'published_at': published_at.strip(),
                'source_url': article_url.strip()
            }
            
            # INSERT実行
            if self.insert_scout_comment(scout_data):
                results["inserted"] += 1
            else:
                results["duplicates"] += 1
        
        print(f"[{mode_text}] INSERT完了: {results['inserted']}件挿入, {results['duplicates']}件重複, {results['errors']}件エラー")
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
            f"-- 生成日時: {now_jst().strftime('%Y-%m-%d %H:%M:%S')}（JST）",
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
    team_name,
    scout_name,
    comment,
    published_at,
    source_url
) VALUES (
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
        print(f"✅ SQLファイルを保存しました: {filepath}")
        return filepath
    
    def generate_resolved_sql_file(self, scout_rows: List[List[str]]) -> str:
        """選手ID解決済みのSQLファイルを生成"""
        sql_content = self.generate_insert_sql_with_resolved_ids(scout_rows)
        filename = f"scout_comments_resolved_{now_jst().strftime('%Y%m%d_%H%M%S')}.sql"
        return self.save_sql_file(sql_content, filename)

class SupabasePlayerPromotionStore:
    """選手候補のリサーチ付き昇格（Phase 6）。
    リサーチ結果(promote_draft JSON)を player_candidates.research_payload に保存し（import_draft）、
    確定後に players/stats/player_achievements を作成して昇格する（commit_promotion）。
    詳細設計: docs/phase6_player_promotion_design.md
    """

    # 昇格案JSON の player 側キー -> players 列（名前違いを吸収）
    _PLAYER_FIELD_MAP = {
        'name': 'name',
        'name_kana': 'name_kana',
        'team': 'team',
        'category': 'category',
        'positions': 'position',   # _text
        'throws': 'throw',
        'bats': 'bat',
        'height_cm': 'height_cm',
        'weight_kg': 'weight_kg',
        'fastball_max': 'fastball_max',
        'breaking_balls': 'breaking_balls',
        'long_throw_m': 'long_throw_m',
        'fifty_m_time': 'fifty_m_time',
        'prefecture': 'prefecture',
        'draft_year': 'draft_year',
        'declared': 'declared',
        'bio': 'bio',
        'description': 'description',
    }

    # stats へ展開する際に拾う列（payload stats のキー = stats 列名）
    _STATS_FIELDS = [
        'year', 'season', 'tournament', 'games',
        'innings', 'era', 'strikeouts', 'strikeouts_per_9', 'whip', 'hits_allowed',
        'batting_avg_against', 'earned_runs', 'walks',
        'at_bats', 'hits', 'home_runs', 'rbis', 'steals', 'avg', 'obp', 'slg', 'ops',
    ]

    _VALID_SEASONS = {'spring', 'summer', 'fall'}  # stats.season は NOT NULL かつこの3値のみ

    _ACHIEVEMENT_FIELDS = ['type', 'year', 'tournament_name', 'result']

    # players はコード値で保持するため、JSON側の日本語表記を変換する
    _CATEGORY_MAP = {'高校': 'high_school', '大学': 'university', '社会人': 'company', '独立リーグ': 'independent', '独立': 'independent'}
    _THROWBAT_MAP = {'右': 'R', '左': 'L', '両': 'S', '両打': 'S', '右投': 'R', '左投': 'L'}

    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode, self.supabase = _init_supabase_client(dummy_mode=dummy_mode)
        if not self.dummy_mode:
            print("✅ Supabaseクライアントを初期化しました（player_candidates 昇格）")

    def fetch_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        if self.dummy_mode or self.supabase is None:
            return None
        try:
            res = (
                self.supabase.table('player_candidates')
                .select('*').eq('id', candidate_id).limit(1).execute()
            )
            rows = res.data or []
            return rows[0] if rows else None
        except Exception as e:
            print(f"[DB] player_candidates 取得エラー: {e}")
            return None

    def list_candidates(self, status: str = 'pending', limit: int = 50) -> List[Dict[str, Any]]:
        """昇格対象の候補一覧を返す（候補選択の補助）。status='all' で全件。"""
        if self.dummy_mode or self.supabase is None:
            return []
        try:
            query = self.supabase.table('player_candidates').select(
                'id,name,team,category,draft_year,status,research_status,player_id'
            )
            if status and status != 'all':
                query = query.eq('status', status)
            res = query.order('created_at', desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            print(f"[DB] player_candidates 一覧取得エラー: {e}")
            return []

    def find_existing_player(self, name: Optional[str], draft_year: Optional[int] = None) -> Optional[str]:
        """同一選手が既に players に存在するか調べ、あれば player_id を返す。
        氏名はスペース等を除去して正規化照合する（手作業INSERT等との重複登録を防ぐ）。
        """
        if self.dummy_mode or self.supabase is None or not name:
            return None
        from utils import normalize_player_key
        norm = normalize_player_key(name)
        if not norm:
            return None
        prefix = norm[:2]  # 姓相当でゆるく絞ってから正規化照合
        try:
            res = self.supabase.table('players').select('id,name,draft_year').ilike('name', f'%{prefix}%').execute()
            rows = res.data or []
        except Exception as e:
            print(f"[DB] players 重複チェックエラー: {e}")
            return None
        for r in rows:
            if normalize_player_key(r.get('name') or '') != norm:
                continue
            if draft_year and r.get('draft_year') and r['draft_year'] != draft_year:
                continue
            return r['id']
        return None

    def import_draft(self, payload: Dict[str, Any]) -> bool:
        """昇格案JSON を player_candidates.research_payload に保存し research_status='ready' にする。"""
        candidate_id = (payload or {}).get('candidate_id')
        if not candidate_id or str(candidate_id).startswith('<'):
            print("[Promotion] candidate_id が未設定のためスキップ（payloadに実UUIDを入れてください）")
            return False
        if self.dummy_mode or self.supabase is None:
            print(f"[Promotion] (dummy) import {candidate_id}")
            return True

        candidate = self.fetch_candidate(candidate_id)
        if not candidate:
            print(f"[Promotion] candidate が見つかりません: {candidate_id}")
            return False
        if candidate.get('status') == 'promoted' or candidate.get('research_status') == 'committed':
            print(f"[Promotion] 既に昇格済みのためimportスキップ: {candidate_id}")
            return False

        try:
            self.supabase.table('player_candidates').update({
                'research_payload': payload,
                'research_status': 'ready',
                'researched_at': now_jst().isoformat(),
            }).eq('id', candidate_id).execute()
            print(f"[Promotion] import完了 → ready: {candidate_id}")
            return True
        except Exception as e:
            print(f"[DB] research_payload 保存エラー: {e}")
            return False

    def commit_promotion(self, candidate_id: str) -> Optional[str]:
        """ready の候補を players/stats/player_achievements に展開して昇格する。"""
        if self.dummy_mode or self.supabase is None:
            print(f"[Promotion] (dummy) commit {candidate_id}")
            return None

        candidate = self.fetch_candidate(candidate_id)
        if not candidate:
            print(f"[Promotion] candidate が見つかりません: {candidate_id}")
            return None
        if candidate.get('player_id') or candidate.get('status') == 'promoted' or candidate.get('research_status') == 'committed':
            print(f"[Promotion] 既に昇格済みのためcommitスキップ: {candidate_id}")
            return candidate.get('player_id')

        payload = candidate.get('research_payload')
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not payload or not payload.get('player'):
            print(f"[Promotion] research_payload が無い/不正のためスキップ: {candidate_id}")
            return None

        player = payload['player']

        # 0) 既存playerの重複チェック（手作業INSERT等との衝突防止＋氏名表記ゆれの名寄せ）
        existing_id = self.find_existing_player(player.get('name'), player.get('draft_year'))
        if existing_id:
            print(f"[Promotion] 既存playerが見つかりました（新規INSERTは行いません）: player_id={existing_id}")
            print(f"            candidate={candidate_id} を既存playerにリンクします（stats/achievementsは既存を尊重しスキップ）")
            try:
                self.supabase.rpc('promote_player_candidate_links', {
                    'p_player_candidate_id': candidate_id,
                    'p_player_id': existing_id,
                }).execute()
            except Exception as e:
                print(f"[DB] promote_player_candidate_links エラー: {e}")
            try:
                self.supabase.table('player_candidates').update({
                    'research_status': 'committed',
                }).eq('id', candidate_id).execute()
            except Exception as e:
                print(f"[DB] research_status 更新エラー: {e}")
            print(f"[Promotion] 既存playerへのリンク完了: candidate={candidate_id} → player={existing_id}")
            return existing_id

        # 1) players へ INSERT（列マッピング・rank=0固定）
        player_row = self._build_player_row(player)
        try:
            res = self.supabase.table('players').insert(player_row).execute()
            player_id = (res.data or [{}])[0].get('id')
        except Exception as e:
            print(f"[DB] players INSERT エラー: {e}")
            return None
        if not player_id:
            print(f"[Promotion] player_id 取得失敗: {candidate_id}")
            return None

        # 2) stats へ INSERT（period=選手の段階。投手/打撃は innings/at_bats 列で区別）
        category_code = self._CATEGORY_MAP.get(player.get('category'), player.get('category'))
        stats_rows = self._build_stats_rows(payload.get('stats') or [], player_id, category_code)
        if stats_rows:
            try:
                self.supabase.table('stats').insert(stats_rows).execute()
            except Exception as e:
                print(f"[DB] stats INSERT エラー: {e}")

        # 3) player_achievements へ INSERT
        ach_rows = self._build_achievement_rows(payload.get('achievements') or [], player_id)
        if ach_rows:
            try:
                self.supabase.table('player_achievements').insert(ach_rows).execute()
            except Exception as e:
                print(f"[DB] player_achievements INSERT エラー: {e}")

        # 4) リンク伝播（scout_comments/attention_signals/scout_visits の player_id 更新＋candidate.status='promoted'）
        try:
            self.supabase.rpc('promote_player_candidate_links', {
                'p_player_candidate_id': candidate_id,
                'p_player_id': player_id,
            }).execute()
        except Exception as e:
            print(f"[DB] promote_player_candidate_links エラー: {e}")

        # 5) research_status='committed'
        try:
            self.supabase.table('player_candidates').update({
                'research_status': 'committed',
            }).eq('id', candidate_id).execute()
        except Exception as e:
            print(f"[DB] research_status 更新エラー: {e}")

        print(f"[Promotion] commit完了: candidate={candidate_id} → player={player_id}")
        return player_id

    def _build_player_row(self, player: Dict[str, Any]) -> Dict[str, Any]:
        row: Dict[str, Any] = {}
        for src_key, dst_col in self._PLAYER_FIELD_MAP.items():
            value = player.get(src_key)
            if value is None:
                continue
            if src_key == 'category':
                value = self._CATEGORY_MAP.get(value, value)
            elif src_key in ('throws', 'bats'):
                value = self._THROWBAT_MAP.get(value, value)
            row[dst_col] = value
        row['rank'] = 0  # 運営が手動設定。リサーチ値は使わない
        return row

    def _build_stats_rows(self, stats: List[Dict[str, Any]], player_id: str, period: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = []
        skipped = 0
        for s in stats:
            if s.get('season') not in self._VALID_SEASONS:
                skipped += 1
                continue
            row = {k: s[k] for k in self._STATS_FIELDS if s.get(k) is not None}
            if not row:
                continue
            row['player_id'] = player_id
            if period:
                row['period'] = period  # 段階(high_school/university/company)。投手/打撃は innings/at_bats 列で区別
            rows.append(row)
        if skipped:
            print(f"[Promotion] season未指定/不正の stats を {skipped}件スキップ（season は spring/summer/fall 必須）")
        return rows

    def _build_achievement_rows(self, achievements: List[Dict[str, Any]], player_id: str) -> List[Dict[str, Any]]:
        rows = []
        for a in achievements:
            row = {k: a[k] for k in self._ACHIEVEMENT_FIELDS if a.get(k) is not None}
            if not row:
                continue
            row['player_id'] = player_id
            rows.append(row)
        return rows


def import_player_promotion_draft(payload: Dict[str, Any], dummy_mode: bool = False) -> bool:
    """昇格案JSON(payload) を player_candidates に取り込む（Phase 6 import-draft）。"""
    store = SupabasePlayerPromotionStore(dummy_mode=dummy_mode)
    return store.import_draft(payload)


def commit_player_promotions(candidate_ids: List[str], dummy_mode: bool = False) -> Dict[str, int]:
    """ready の候補を players/stats/player_achievements に展開して昇格する（Phase 6 commit）。"""
    store = SupabasePlayerPromotionStore(dummy_mode=dummy_mode)
    stats = {'committed': 0, 'skipped': 0, 'errors': 0}
    for cid in candidate_ids:
        try:
            player_id = store.commit_promotion(cid)
            if player_id:
                stats['committed'] += 1
            else:
                stats['skipped'] += 1
        except Exception as e:
            print(f"[Promotion] commitエラー {cid}: {e}")
            stats['errors'] += 1
    return stats


def list_promotion_candidates(status: str = 'pending', limit: int = 50, dummy_mode: bool = False) -> List[Dict[str, Any]]:
    """昇格対象候補の一覧を返す（Phase 6 候補選択の補助）。"""
    store = SupabasePlayerPromotionStore(dummy_mode=dummy_mode)
    return store.list_candidates(status=status, limit=limit)


def promote_player_from_draft(payload: Dict[str, Any], dummy_mode: bool = False) -> Optional[str]:
    """昇格案JSON を取り込み（import）、そのまま昇格（commit）まで一気に行う（Phase 6 一気通貫）。"""
    store = SupabasePlayerPromotionStore(dummy_mode=dummy_mode)
    if not store.import_draft(payload):
        return None
    return store.commit_promotion(payload.get('candidate_id'))


def generate_scout_comment_sql_with_resolved_ids(scout_rows: List[List[str]], dummy_mode: bool = False) -> str:
    """選手ID解決済みのスカウトコメントSQLを生成（簡易版）"""
    generator = SupabaseScoutCommentGenerator(dummy_mode=dummy_mode)
    return generator.generate_insert_sql_with_resolved_ids(scout_rows)

def insert_scout_comments_directly(scout_rows: List[List[str]], dummy_mode: bool = False) -> Dict[str, int]:
    """スカウトコメントをデータベースに直接INSERT"""
    inserter = SupabaseScoutCommentInserter(dummy_mode=dummy_mode)
    return inserter.insert_multiple_scout_comments(scout_rows)

def insert_player_candidates(articles: List[Dict[str, Any]], dummy_mode: bool = False) -> Dict[str, int]:
    """未登録選手候補を player_candidates にINSERT"""
    store = SupabasePlayerCandidateStore(dummy_mode=dummy_mode)
    return store.insert_unregistered_candidates(articles)

def insert_attention_signals(articles: List[Dict[str, Any]], dummy_mode: bool = False) -> Dict[str, int]:
    """注目度シグナルを attention_signals にINSERT"""
    store = SupabaseAttentionSignalStore(dummy_mode=dummy_mode)
    return store.insert_attention_signals(articles)

def insert_scout_visits(articles: List[Dict[str, Any]], dummy_mode: bool = False) -> Dict[str, int]:
    """視察情報を scout_visits にINSERT"""
    store = SupabaseScoutVisitStore(dummy_mode=dummy_mode)
    return store.insert_scout_visits(articles)

def process_draft_watch_candidates(dummy_mode: bool = False) -> Dict[str, int]:
    """
    Draft-Watch記事候補のトピック判定・更新・下書き生成を行う（Phase 4: 1日1回の朝バッチ専用）。
    前回バッチ以降に蓄積された attention_signals を起点に処理する。
    """
    store = SupabaseDraftWatchCandidateStore(dummy_mode=dummy_mode)
    return store.process_new_signals()

def regenerate_draft_watch_drafts(only_missing: bool = False, dummy_mode: bool = False) -> Dict[str, int]:
    """
    既存のDraft-Watch候補（status=draft）について summary_json / importance_score / 下書き本文を作り直す。
    プロンプト改善を既存候補へ反映したいときに使う（新着シグナルの有無に依存しない）。
    only_missing=True なら本文が未生成の候補だけを対象にする。
    """
    store = SupabaseDraftWatchCandidateStore(dummy_mode=dummy_mode)
    return store.regenerate_all_drafts(only_missing=only_missing)

def get_existing_crawled_urls_by_source(source: str, dummy_mode: bool = False) -> Set[str]:
    """crawled_articles から指定ソースの既存URLを取得"""
    store = SupabaseCrawledArticleStore(dummy_mode=dummy_mode)
    return store.get_existing_urls_by_source(source)

def get_existing_crawled_urls(dummy_mode: bool = False) -> Set[str]:
    """crawled_articles から全既存URLを取得"""
    store = SupabaseCrawledArticleStore(dummy_mode=dummy_mode)
    return store.get_existing_urls()

def upsert_crawled_articles(articles: List[Dict[str, Any]], dummy_mode: bool = False) -> Dict[str, int]:
    """crawled_articles に記事をupsert"""
    store = SupabaseCrawledArticleStore(dummy_mode=dummy_mode)
    return store.upsert_articles(articles)
