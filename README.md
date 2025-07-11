# Draft News Crawler

野球記事収集・AIコメント抽出システム

## 概要

プロ野球のドラフト候補に関する記事を自動収集し、AIを使用してスカウトコメントを抽出するシステムです。

## 主な機能

- **記事自動収集**: 5つのメディアから野球記事を自動収集
- **AIコメント抽出**: Google Gemini AIを使用してスカウトコメントを自動抽出
- **選手データベース連携**: Supabaseデータベースから選手情報を取得
- **SQL自動生成**: スカウトコメントをデータベースに挿入するSQL文を自動生成
- **Google Sheets連携**: 記事情報とスカウトコメントをスプレッドシートに自動更新
- **重複除去**: 既存記事との重複を自動チェック

## 対応メディア

- スポニチ
- スポーツ報知
- 日刊スポーツ
- サンスポ
- 中日スポーツ

## GitHub Actions設定

### 必要なSecrets設定

1. **GOOGLE_CREDENTIALS_BASE64**: Google Sheets API認証情報
   ```bash
   # credentials.jsonをbase64エンコード
   base64 -i credentials.json
   ```

2. **GOOGLE_GENAI_API_KEY**: Gemini API認証キー

3. **SUPABASE_URL**: SupabaseプロジェクトのURL
   ```
   https://your-project-id.supabase.co
   ```

4. **SUPABASE_KEY**: Supabaseのanon public key

### 設定手順

1. GitHubリポジトリのSettings > Secrets and variables > Actions
2. 上記の4つのSecretsを追加
3. ワークフローは毎日9:00、15:00、21:00（JST）に自動実行
4. 手動実行も可能（Actionsタブから）

## ローカル実行

```bash
pip install -r requirements.txt
python main_new.py
```

## 出力

- Google Sheets: 記事データとスカウトコメント
- コンソール: 実行ログと統計情報