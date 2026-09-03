"""
プロ志望届まとめ記事のSupabase入出力。

- players 全件ロード（名寄せ用）
- players.declared の false → true 更新
- draft_watch_article_candidates の「志望届まとめ」1行を作成/更新
- 公開済みの場合は articles 本体と article_players（記事と選手の紐付け）も同期
"""

from typing import Any, Dict, List, Optional

from database.supabase_client import _init_supabase_client, now_jst

# PostgRESTのselectは1回1000件が上限のため、全件取得はページングする。
PAGE_SIZE = 1000


class ProAspiringStore:
    def __init__(self, dummy_mode: bool = False):
        self.dummy_mode, self.supabase = _init_supabase_client(dummy_mode=dummy_mode)
        if not self.dummy_mode:
            print("✅ Supabaseクライアントを初期化しました（プロ志望届）")

    # ------------------------------------------------------------------ players

    def load_players(self) -> List[Dict[str, Any]]:
        if self.dummy_mode or self.supabase is None:
            return []
        rows: List[Dict[str, Any]] = []
        start = 0
        while True:
            response = (
                self.supabase
                .table('players')
                .select('id,name,name_kana,team,category,draft_year,declared')
                .range(start, start + PAGE_SIZE - 1)
                .execute()
            )
            page = response.data or []
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                break
            start += PAGE_SIZE
        return rows

    def set_declared(self, player_ids: List[str]) -> int:
        """declared を true にする。対象が無ければ何もしない。"""
        if not player_ids or self.dummy_mode or self.supabase is None:
            return 0
        updated = 0
        for player_id in player_ids:
            try:
                self.supabase.table('players').update({
                    'declared': True,
                    'updated_at': now_jst().isoformat(),
                }).eq('id', player_id).execute()
                updated += 1
            except Exception as e:
                print(f"[DB] players.declared 更新エラー ({player_id}): {e}")
        return updated

    # ------------------------------------------- draft_watch_article_candidates

    def find_candidate(self, topic_key: str) -> Optional[Dict[str, Any]]:
        if self.dummy_mode or self.supabase is None:
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
            print(f"[DB] draft_watch_article_candidates 取得エラー: {e}")
            return None

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

    def add_sources(self, candidate_id: str, source_urls: List[str]) -> None:
        """出典テーブルへ名簿ページのURLを登録する（重複はunique制約で弾かれる）。"""
        if self.dummy_mode or self.supabase is None:
            return
        try:
            existing = (
                self.supabase
                .table('draft_watch_article_candidate_sources')
                .select('source_url')
                .eq('draft_watch_article_candidate_id', candidate_id)
                .execute()
            ).data or []
        except Exception as e:
            print(f"[DB] 出典取得エラー: {e}")
            existing = []

        known = {row.get('source_url') for row in existing}
        for url in source_urls:
            if url in known:
                continue
            try:
                self.supabase.table('draft_watch_article_candidate_sources').insert({
                    'draft_watch_article_candidate_id': candidate_id,
                    'crawled_article_id': None,
                    'source_url': url,
                    'role': 'primary',
                }).execute()
            except Exception as e:
                print(f"[DB] 出典追加スキップ ({url}): {e}")

    # ---------------------------------------------- 公開記事（articles）との同期

    def sync_published_article(self, article_id: str, title: str, content: str, excerpt: str) -> bool:
        """
        候補が公開済みの場合、公開記事本体の本文も同じ内容へ更新する。
        名簿は提出があるたびに増えるので、公開後も中身を追随させる必要がある。
        """
        if self.dummy_mode or self.supabase is None:
            return False
        try:
            self.supabase.table('articles').update({
                'title': title,
                'content': content,
                'excerpt': excerpt,
                'updated_at': now_jst().isoformat(),
            }).eq('id', article_id).execute()
            return True
        except Exception as e:
            print(f"[DB] articles 更新エラー: {e}")
            return False

    def sync_article_players(self, article_id: str, player_ids: List[str]) -> int:
        """記事と選手の紐付けを追加する（既存分は触らない）。"""
        if not article_id or self.dummy_mode or self.supabase is None:
            return 0
        try:
            existing = (
                self.supabase
                .table('article_players')
                .select('player_id')
                .eq('article_id', article_id)
                .execute()
            ).data or []
        except Exception as e:
            print(f"[DB] article_players 取得エラー: {e}")
            return 0

        known = {row.get('player_id') for row in existing}
        new_rows = [
            {'article_id': article_id, 'player_id': player_id}
            for player_id in player_ids
            if player_id not in known
        ]
        if not new_rows:
            return 0
        try:
            self.supabase.table('article_players').insert(new_rows).execute()
            return len(new_rows)
        except Exception as e:
            print(f"[DB] article_players 追加エラー: {e}")
            return 0
