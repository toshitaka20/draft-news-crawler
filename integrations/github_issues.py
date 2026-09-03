"""
GitHub Issue クライアント（REST API）。

志望届を出したのに players 未登録の選手を、Phase 6（選手候補の昇格）の作業チケットとして
Issueで管理するために使う。選手ごとにIssueを乱立させず、年ごとの「トラッカーIssue」1本を
毎回書き換える運用なので、タイトルでIssueを引く / 本文を更新する / コメントを足す、が揃っている。

トークンは GH_TOKEN / GITHUB_TOKEN、無ければ `gh auth token` から取得する。
どちらも無ければ available=False になり、呼び出し側はIssue操作をスキップする。
"""

import os
import re
import subprocess
from typing import Any, Dict, List, Optional

import requests

API_ROOT = 'https://api.github.com'
REQUEST_TIMEOUT = 20


def _detect_repo() -> Optional[str]:
    repo = os.getenv('GITHUB_REPOSITORY')
    if repo:
        return repo
    try:
        url = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except Exception:
        return None
    match = re.search(r'github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/\s]+?)(?:\.git)?$', url)
    return f"{match.group('owner')}/{match.group('name')}" if match else None


def _detect_token() -> Optional[str]:
    token = os.getenv('GH_TOKEN') or os.getenv('GITHUB_TOKEN')
    if token:
        return token
    try:
        result = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    token = result.stdout.strip()
    return token if result.returncode == 0 and token else None


class GitHubIssueClient:
    def __init__(self, repo: Optional[str] = None, token: Optional[str] = None, dry_run: bool = False):
        self.repo = repo or _detect_repo()
        self.token = token or _detect_token()
        self.dry_run = dry_run

    @property
    def available(self) -> bool:
        return bool(self.repo and self.token)

    def _headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }

    def ensure_label(self, name: str, color: str = 'ededed', description: str = '') -> bool:
        """ラベルが無ければ作る（既にあれば422が返るので成功扱い）。"""
        if not self.available or self.dry_run:
            return False
        try:
            response = requests.post(
                f'{API_ROOT}/repos/{self.repo}/labels',
                headers=self._headers(),
                json={'name': name, 'color': color, 'description': description},
                timeout=REQUEST_TIMEOUT,
            )
            return response.status_code in (201, 422)
        except Exception as e:
            print(f"[GitHub] ラベル作成エラー ({name}): {e}")
            return False

    def list_issues(self, label: str) -> List[Dict[str, Any]]:
        """指定ラベルのIssue一覧（open/closed両方）。"""
        if not self.available:
            return []
        issues: List[Dict[str, Any]] = []
        page = 1
        while page <= 10:
            try:
                response = requests.get(
                    f'{API_ROOT}/repos/{self.repo}/issues',
                    headers=self._headers(),
                    params={'labels': label, 'state': 'all', 'per_page': 100, 'page': page},
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
            except Exception as e:
                print(f"[GitHub] Issue一覧取得エラー: {e}")
                break
            rows: List[Dict[str, Any]] = response.json() or []
            # issues API は PR も返すので除外する。
            issues.extend(row for row in rows if 'pull_request' not in row)
            if len(rows) < 100:
                break
            page += 1
        return issues

    def get_issue(self, number: int) -> Optional[Dict[str, Any]]:
        if not self.available:
            return None
        try:
            response = requests.get(
                f'{API_ROOT}/repos/{self.repo}/issues/{number}',
                headers=self._headers(), timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[GitHub] Issue取得エラー (#{number}): {e}")
            return None

    def find_issue_by_title(self, label: str, title: str) -> Optional[Dict[str, Any]]:
        for issue in self.list_issues(label):
            if (issue.get('title') or '').strip() == title.strip():
                return issue
        return None

    def update_issue(self, number: int, body: str, title: Optional[str] = None) -> bool:
        if self.dry_run:
            print(f"[GitHub] (dry-run) Issue本文を更新: #{number}")
            return False
        if not self.available:
            return False
        payload: Dict[str, Any] = {'body': body}
        if title:
            payload['title'] = title
        try:
            response = requests.patch(
                f'{API_ROOT}/repos/{self.repo}/issues/{number}',
                headers=self._headers(), json=payload, timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            print(f"[GitHub] Issue本文を更新: #{number}")
            return True
        except Exception as e:
            print(f"[GitHub] Issue更新エラー (#{number}): {e}")
            return False

    def create_comment(self, number: int, body: str) -> bool:
        if self.dry_run:
            print(f"[GitHub] (dry-run) Issueへコメント: #{number}")
            return False
        if not self.available:
            return False
        try:
            response = requests.post(
                f'{API_ROOT}/repos/{self.repo}/issues/{number}/comments',
                headers=self._headers(), json={'body': body}, timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            print(f"[GitHub] Issueへコメント: #{number}")
            return True
        except Exception as e:
            print(f"[GitHub] コメント作成エラー (#{number}): {e}")
            return False

    def create_issue(self, title: str, body: str, labels: List[str]) -> Optional[int]:
        if self.dry_run:
            print(f"[GitHub] (dry-run) Issue作成: {title}")
            return None
        if not self.available:
            return None
        try:
            response = requests.post(
                f'{API_ROOT}/repos/{self.repo}/issues',
                headers=self._headers(),
                json={'title': title, 'body': body, 'labels': labels},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            number = response.json().get('number')
            print(f"[GitHub] Issue作成: #{number} {title}")
            return number
        except Exception as e:
            print(f"[GitHub] Issue作成エラー ({title}): {e}")
            return None
