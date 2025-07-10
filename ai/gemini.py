"""
Gemini API連携・コメント抽出
"""

import google.generativeai as genai  # type: ignore
import csv
from typing import List, Dict, Any, Optional
from config import GEMINI_API_KEY, GEMINI_MODEL, AI_KEYWORDS

def contains_keywords(text: str, keywords: List[str]) -> bool:
    """
    テキストにキーワードが含まれているかチェック
    """
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)

def setup_gemini():
    """
    Gemini APIの初期設定
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEYが設定されていません")
    
    genai.configure(api_key=GEMINI_API_KEY)  # type: ignore
    return genai.GenerativeModel(GEMINI_MODEL)  # type: ignore

def extract_scout_comments_with_gemini(article_text: str, title: str, published: str, link: str) -> Optional[str]:
    """
    記事からスカウトコメントを抽出（超高精度版）
    """
    try:
        model = setup_gemini()
        
        prompt = f"""
あなたはプロ野球のスカウトコメント抽出AIです。
以下の記事本文から、プロ野球・MLB・侍ジャパン監督などの「球団スカウト」が特定の選手について述べた評価コメント・発言を抽出してください。

【重要：抽出対象の厳密な定義】
1. 発言者：以下のいずれかに該当する人物のみ
   - プロ野球球団のスカウト・スカウト部長・スカウト担当者
   - プロ野球球団の監督・コーチ・GM・球団関係者
   - MLB球団のスカウト・監督・コーチ・GM
   - 侍ジャパンの監督・コーチ・関係者
   - 明確に「スカウト」「GM」と明記されている人物

2. 発言内容：以下の条件をすべて満たすもののみ
   - 選手の能力・技術・特徴・評価についての具体的な発言
   - 明確に「」や『』で囲まれた発言、または「〜と語る」「〜と評価」「〜とコメント」「〜と太鼓判を押した」「〜と評した」「〜と話した」などの形で引用されている発言
   - 選手の名前が明確に特定できる発言
   - 発言者の名前・所属が明確、または「スカウト」「GM」など役職が明記されている発言

【厳格な除外対象】
- 選手本人の発言・コメント（絶対に抽出しない）
  - 「〜選手は〜と語った」「〜選手が〜とコメント」の後の発言内容
  - 「〜選手は〜と振り返った」「〜選手は〜と話した」の後の発言内容
  - 選手の自己評価や目標発言
  - 選手の感想や心境を表す発言
- 記者・ライターの分析・評価・推測
- ファン・一般の人の意見
- 明確な発言ではなく推測・憶測の記述
- 選手名が特定できない曖昧な発言
- 発言者名・役職が不明な発言

【選手発言の除外パターン】
以下のパターンは選手本人の発言なので絶対に抽出しない：
- 「〜と喜んだ」「〜と悔しがった」「〜と笑顔で語った」
- 「〜と意気込みを語った」「〜と抱負を語った」

【抽出精度の向上】
- 発言が明確に存在しない場合は「コメントなし」と出力
- 発言が曖昧で判断できない場合は除外
- 複数の発言がある場合は、それぞれを個別の行として出力
- 発言者の所属が不明な場合は「不明」と表記
- 選手本人の発言は絶対に抽出しない

【発言者の特定】
- 「〜スカウトが〜と評価」→ スカウト名を抽出
- 「〜監督が〜と語る」→ 監督名を抽出
- 「〜GMが〜とコメント」→ GM名を抽出
- 役職のみ明記されている場合は「匿名スカウト」「匿名監督」などで表記

【球団名の英語表記ルール】
- 日本プロ野球球団は英語で表記してください
- 巨人 → giants
- 阪神 → tigers  
- 中日 → dragons
- 広島 → carp
- 横浜DeNA → baystars
- ヤクルト → swallows
- 西武 → lions
- 日本ハム → fighters
- ロッテ → marines
- ソフトバンク → hawks
- オリックス → buffaloes
- 楽天 → eagles
- メジャーリーグ球団（匿名） → MLB
- メジャーリーグ球団（名前あり） → その球団名（例：マリナーズ）
- 侍ジャパン → 侍ジャパン
- その他の球団・組織 → other

【出力カラム】
選手名, 選手所属チーム, スカウト名, スカウト球団名, コメント内容, published_at, 記事URL

【選手名の取得ルール】
- 選手名は必ずフルネーム（姓+名）で取得してください
- 「田中」「佐藤」などの姓のみは使用しない
- 記事内でフルネームが明記されている場合はそれを使用
- フルネームが不明な場合は「不明」と表記

【出力形式】
- カンマ区切り（CSV形式、1行目はカラム名（ヘッダー））
- 2行目以降がデータ
- 1コメントにつき1行
- 明確なスカウトコメントが存在しない場合は「コメントなし」のみ出力

【記事情報】
タイトル: {title}
公開日: {published}
URL: {link}

【本文】
{article_text}
"""
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        print(f"[Generative AI Geminiエラー] {e}")
        return None

def process_articles_with_ai(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    記事リストにAIコメント抽出を適用（キーワードがある記事のみ）
    """
    processed_articles = []
    keyword_count = 0  # ← カウント用
    
    for article in articles:
        scout_rows = []  # ← 各記事ごとに初期化
        # キーワードがある記事のみAI処理を実行
        has_keywords = article.get('has_keywords', False)
        
        if has_keywords:
            keyword_count += 1  # ← カウント
            try:
                # 記事のタイトルと本文を結合
                full_text = f"{article.get('title', '')}\n\n{article.get('body', '')}"
                
                print(f"[DEBUG] AI処理実行: {article.get('title', '')[:50]}...")
                
                # AIでコメント抽出（CSV形式）
                scout_csv = extract_scout_comments_with_gemini(
                    full_text, 
                    article.get('title', ''), 
                    article.get('date', ''), 
                    article.get('url', '')
                )
                
                # スカウトコメントをCSVパースして別シート用データに追加
                if scout_csv:
                    try:
                        reader = csv.reader(scout_csv.strip().splitlines())
                        rows_list = list(reader)
                        # 1行目はヘッダーなのでスキップ
                        for row in rows_list[1:]:
                            if len(row) == 7:
                                # 記事公開日のフォーマットを統一（timestamp with time zone形式）
                                from utils import format_timestamp
                                processed_row = list(row)
                                processed_row[5] = format_timestamp(row[5])  # 記事公開日（6列目）をフォーマット
                                scout_rows.append(processed_row)
                    except Exception as e:
                        print(f"[スカウトコメントCSVパースエラー] {e}")
                
                # 結果を追加
                article['scout_comments'] = scout_csv or "コメントなし"
                
            except Exception as e:
                print(f"[エラー] 記事AI処理失敗: {article.get('title', '')} - {e}")
                article['scout_comments'] = "エラー: 処理に失敗しました"
        else:
            # キーワードがない記事はスカウトコメントなし
            article['scout_comments'] = "キーワードなし"
            print(f"[DEBUG] キーワードなし、AI処理スキップ: {article.get('title', '')[:50]}...")
        
        article['scout_rows'] = scout_rows  # ← 各記事ごとにセット
        processed_articles.append(article)
    
    print(f"[DEBUG] has_keywords=True の記事数: {keyword_count}")
    return processed_articles 