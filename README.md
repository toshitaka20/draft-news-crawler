# Draft News Crawler

野球記事収集・AIコメント抽出システム

## 概要

プロ野球のドラフト候補に関する記事を自動収集し、AIを使用してスカウトコメントを抽出するシステムです。

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

### 設定手順

1. GitHubリポジトリのSettings > Secrets and variables > Actions
2. 上記の2つのSecretsを追加
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