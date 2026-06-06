import os
import re
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
    def _infer_draft_year(row: Dict[str, Any]) -> Optional[int]:
        draft_year = SupabasePlayerCandidateStore._to_int(row.get('draft_year'))
        if draft_year:
            return draft_year

        published_at = str(row.get('published_at') or '')
        match = re.search(r'(20\d{2})', published_at)
        if match:
            return int(match.group(1))

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

    def insert_unregistered_candidates(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        rows = []
        for article in articles:
            rows.extend(article.get('player_candidate_rows', []))

        if not rows:
            return {'total': 0, 'inserted': 0, 'skipped_existing_players': 0, 'duplicates': 0, 'errors': 0}

        if self.dummy_mode or self.supabase is None:
            print(f"[DB] player_candidates 保存スキップ（ダミーモード）: {len(rows)}件")
            return {
                'total': len(rows),
                'inserted': 0,
                'sources_inserted': 0,
                'skipped_existing_players': 0,
                'duplicates': 0,
                'errors': 0,
            }

        source_urls = [row.get('source_url', '') for row in rows if row.get('source_url')]
        crawled_id_map = SupabaseCrawledArticleStore(dummy_mode=False).get_article_id_map_by_urls(source_urls)
        player_id_map = self.player_lookup.lookup_multiple_players([row.get('name', '') for row in rows])

        candidate_inputs = []
        skipped_existing_players = 0
        duplicates = 0

        for row in rows:
            name = self._clean_text(row.get('name'))
            source_url = self._clean_text(row.get('source_url'))
            if not name or not source_url:
                continue

            player_id = player_id_map.get(name)
            if player_id is not None:
                skipped_existing_players += 1
                continue

            team_name = self._clean_text(row.get('team_name'))
            team = self._clean_text(row.get('team')) or team_name
            category = self._normalize_category(row.get('category') or row.get('article_category'))
            draft_year = self._infer_draft_year(row)
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
                'position': self._clean_text(row.get('position')),
                'throws': self._clean_text(row.get('throws')),
                'bats': self._clean_text(row.get('bats')),
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
                'skipped_existing_players': skipped_existing_players,
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
                'skipped_existing_players': skipped_existing_players,
                'duplicates': duplicates,
                'errors': len(source_records),
            }

        self._refresh_candidate_source_summaries(sorted({record['player_candidate_id'] for record in source_records}))
        return {
            'total': len(rows),
            'inserted': inserted,
            'sources_inserted': sources_inserted,
            'skipped_existing_players': skipped_existing_players,
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

            teams = [team.strip() for team in str(row[7] or '').split(',') if team.strip()]
            records.append({
                'crawled_article_id': crawled_id_map.get(source_url),
                'player_id': None,
                'player_candidate_id': None,
                'player_name': None,
                'source_url': source_url,
                'source_title': str(row[3] or '').strip() or None,
                'published_at': self._format_published_at(row[0]),
                'source': str(row[1] or '').strip() or None,
                'category': str(row[2] or '').strip() or None,
                'team_count': self._to_int(row[5]),
                'person_count': self._to_int(row[6]),
                'teams': teams,
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
            
            # データを正規化
            scout_data = {
                'player_id': player_id,
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
