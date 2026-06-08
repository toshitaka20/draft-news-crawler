"""
Gemini API連携・コメント抽出
"""

import google.generativeai as genai  # type: ignore
import csv
import json
import re
from typing import List, Dict, Any, Optional
from config import GEMINI_API_KEY, GEMINI_MODEL
from utils import normalize_team_key, ALL_NPB_TEAM_KEYS

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
あなたはプロ野球のドラフト評価コメント抽出AIです。
以下の記事本文から、NPB・MLB球団のスカウト、編成担当、GMなどのドラフト評価担当者が、特定の選手について述べた評価コメント・発言だけを抽出してください。

【重要：抽出対象の厳密な定義】
1. 発言者：以下のいずれかに該当する人物のみ
   - プロ野球球団のスカウト・スカウト部長・スカウト担当者
   - プロ野球球団の編成部長・編成副部長・編成部部長・編成本部長・編成本部長代理・編成本部参与・編成ディレクター・球団本部長・球団本部副本部長・統括本部長・GM・GM補佐・GM特別補佐・CBOなどドラフトや編成に関わる球団関係者
   - 役職名が「チーフ」「チーフ補佐」「グループ長」「ディレクター」「スーパーバイザー」「アドバイザー」「顧問」「参与」「主任」「補佐」「デスク」「マネージャー」など曖昧でも、文脈上スカウト部・編成部・球団本部・育成/ドラフト担当である人物
   - MLB球団のスカウト・GM・編成担当者
   - 明確に「スカウト」「GM」「編成」「球団本部」と明記されている人物

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
- 高校・大学・社会人・独立リーグなど、選手所属チームの監督・コーチ・部長・関係者の発言
- プロ野球球団の一軍監督・二軍監督・コーチの発言
- 侍ジャパン監督・コーチ・関係者の発言
- 解説者・OB・元監督・元選手の発言
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

【発言者の特定・表記ルール】
- 発言者名は「苗字＋役職名」の形式で表記してください
- 例：「田中スカウト」「山田GM」「鈴木統括本部長」「高橋スカウト部長」
- 「〜スカウトが〜と評価」→ 「○○スカウト」として抽出
- 「〜GMが〜とコメント」→ 「○○GM」として抽出
- 「〜統括本部長が〜と語る」→ 「○○統括本部長」として抽出
- 「〜スカウト部長が〜と評価」→ 「○○スカウト部長」として抽出
- 「〜編成部長が〜とコメント」→ 「○○編成部長」として抽出
- 「〜編成本部長が〜と称賛」→ 「○○編成本部長」として抽出
- 「〜編成本部参与が〜と評価」→ 「○○編成本部参与」として抽出
- 「〜スーパーバイザーが〜と評価」「〜チーフが〜と話した」など、球団のスカウト・編成文脈の肩書きなら抽出
- 役職のみ明記されている場合は「匿名スカウト」「匿名GM」「匿名編成部長」などで表記
- フルネームが記載されている場合でも苗字のみ使用（例：田中太郎スカウト → 田中スカウト）
- 「監督」「コーチ」の肩書きしかない発言者は抽出しない

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
- NPB球団（匿名・球団名不明） → other
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

【出力例】
選手名, 選手所属チーム, スカウト名, スカウト球団名, コメント内容, published_at, 記事URL
田中太郎, ○○高校, 佐藤スカウト, giants, 非常に良いピッチャーです, 2025-07-11T15:30:00+09:00, https://example.com
山田花子, △△大学, 鈴木統括本部長, tigers, 打撃センスが抜群です, 2025-07-11T15:30:00+09:00, https://example.com

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


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []

    cleaned = text.strip()
    fenced_match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned, flags=re.DOTALL)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    if cleaned == "[]":
        return []

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        array_match = re.search(r'\[.*\]', cleaned, flags=re.DOTALL)
        if not array_match:
            return []
        try:
            parsed = json.loads(array_match.group(0))
        except json.JSONDecodeError:
            return []

    if not isinstance(parsed, list):
        return []

    return [item for item in parsed if isinstance(item, dict)]


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    cleaned = text.strip()
    fenced_match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned, flags=re.DOTALL)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        object_match = re.search(r'\{.*\}', cleaned, flags=re.DOTALL)
        if not object_match:
            return None
        try:
            parsed = json.loads(object_match.group(0))
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None


def extract_player_candidates_with_gemini(article_text: str, title: str, published: str, link: str) -> List[Dict[str, Any]]:
    """
    記事からDraft-Watch未登録候補になりうる選手情報を抽出する。
    """
    try:
        model = setup_gemini()

        prompt = f"""
あなたは日本野球ドラフト候補の構造化データ抽出AIです。
以下の記事から、Draft-Watchの選手DBに登録・確認すべき選手候補だけを抽出してください。

【抽出対象】
- プロ注目、今秋ドラフト候補、ドラフト上位候補、1位候補、指名候補として言及された選手
- NPB/MLBスカウト視察やスカウトコメントの対象になっている選手
- 最速150キロ以上、強打者、主将、全国大会実績など、ドラフト文脈で明確に注目されている選手

【除外対象】
- プロ入り済み選手、監督、コーチ、スカウト、解説者
- 記事内で名前だけ出る対戦相手やチームメイトで、ドラフト注目文脈がない人物
- 姓だけ、名だけなどフルネームが不明な人物

【出力形式】
JSON配列のみを返してください。説明文、Markdown、コードブロックは不要です。
候補がない場合は [] を返してください。

各要素のキー:
- name: フルネーム。必須。
- name_kana: 記事にあれば。なければ null。
- team_name: 所属校・大学・社会人チーム。なければ null。
- category: 高校、大学、社会人、独立リーグ、その他のいずれか。推定できなければ null。
- draft_year: ドラフト対象年。高校3年、大学4年、社会人の大卒2年目・高卒3年目は記事公開年。そこから逆算できなければ null。
- school_year: 学年・社会人年数。例: "4年", "3年", "社会人2年目", "高卒3年目"。なければ null。
- positions: 守備位置の配列。例: ["投手"], ["投手", "外野手"], ["内野手"]。なければ []。
- position: 互換用。主な守備位置を1つ。例: "投手", "内野手", "外野手", "捕手"。なければ null。
- throws: 投。必ず R または L。右投は R、左投は L。不明なら null。
- bats: 打。必ず R、L、S のいずれか。右打は R、左打は L、両打は S。不明なら null。
- height_cm: 身長cmの数値。なければ null。
- weight_kg: 体重kgの数値。なければ null。
- birth_date: YYYY-MM-DD。なければ null。
- fastball_max: 最速球速km/hの数値。投手で記事にあれば。なければ null。
- description: 選手候補としての短い要約。なければ null。
- evidence: 抽出根拠になる記事中の短い文。
- confidence: 0.0-1.0。

【記事情報】
タイトル: {title}
公開日: {published}
URL: {link}

【本文】
{article_text}
"""
        response = model.generate_content(prompt)
        return _parse_json_array(response.text)

    except Exception as e:
        print(f"[Generative AI Gemini 選手候補抽出エラー] {e}")
        return []


def extract_scout_visits_with_gemini(article_text: str, title: str, published: str, link: str) -> List[Dict[str, Any]]:
    """
    記事から「どの球団が、どの選手を、何人で、いつ視察したか」という視察情報を抽出する。
    """
    try:
        model = setup_gemini()

        prompt = f"""
あなたはプロ野球のスカウト視察情報抽出AIです。
以下の記事本文から、「どの球団が」「どの選手を」「何人で」「いつ」視察したかという視察情報をすべて抽出してください。

【抽出対象の定義】
- 球団スカウトが特定の選手を視察・観戦・調査したという記述
- 「○○は○人態勢で視察」「○○球団のスカウトが訪れ」のような表現
- 視察対象の選手名が明記されていないものは抽出しない
- 「NPB全12球団」「12球団」のように、視察に来た球団数が"NPB全体の球団数（12）"と一致する形で書かれている場合、それは実質的に「全球団」を意味するので、is_all_npb_teams を true にして1要素だけ出力する（個別球団ごとに分けなくてよい。team_nameはnullのままでよい）
- 「10球団」「主だった球団」のように、12球団に満たない・全球団かどうか不明な人数・規模で書かれている場合は、is_all_npb_teams は false とし、team_name は null のまま「規模情報」として出力する（その人数の内訳球団は記事から特定できないため、個別球団として展開しない）
- 同じ文や段落の中に、上記のような集合的な表現と、個別の球団名（例: 「巨人の○○、日本ハムの○○も視察」）が両方含まれる場合は、集合表現と個別球団の両方をそれぞれ別要素として出力する（集合表現側はteam_name null、個別球団側はteam_name入りで、互いに重複や矛盾しないよう書き分ける）
- 1つの記事に複数球団・複数選手の視察情報があれば、それぞれ別の要素として出力する

【出力形式】
JSON配列のみを返してください。説明文、Markdown、コードブロックは不要です。
該当する視察情報がなければ [] を返してください。

各要素のキー:
- player_name: 視察対象の選手名。フルネームが分かれば。必須。
- team_name: 視察した球団名。記事中の表記のまま（例: "日本ハム", "ソフトバンク"）。個別球団が特定できなければ null。
- is_all_npb_teams: 視察に来た球団がNPB全12球団（＝全球団）であると記事から判断できる場合は true、そうでなければ false。
- person_count: その球団（または集合的な視察全体）から視察に来た人数の数値。記載がなければ null。
- event_date_text: 視察の時期に関する記事中の表現をそのまま（例: "今月上旬", "5月20日の練習試合"）。なければ null。
- event_date: 視察日をYYYY-MM-DD形式で推定したもの。記事の公開日（{published}）を基準に、相対的な時期表現から推定してください。全く推定できなければ null。
- event_date_precision: 推定の確からしさ。日付が記事中に明記されている場合は "exact"、相対的な表現からの推定なら "approximate"、推定できない場合は "unknown"。
- evidence: 抽出根拠になる記事中の短い文。

【記事情報】
タイトル: {title}
公開日: {published}
URL: {link}

【本文】
{article_text}
"""
        response = model.generate_content(prompt)
        return _parse_json_array(response.text)

    except Exception as e:
        print(f"[Generative AI Gemini 視察情報抽出エラー] {e}")
        return []


def process_articles_with_ai(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    記事リストにAIコメント抽出を適用（スカウトコメント候補記事のみ）
    """
    processed_articles = []
    keyword_count = 0  # ← カウント用
    
    for article in articles:
        scout_rows = []  # ← 各記事ごとに初期化
        # スカウトコメント候補がある記事のみAI処理を実行
        has_keywords = article.get('has_scout_comment_candidate', article.get('has_keywords', False))
        
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
                                processed_row = [cell.strip() for cell in row]
                                if processed_row[3].lower() in ('unknown', '不明', ''):
                                    processed_row[3] = 'other'
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
            # 候補がない記事はスカウトコメントなし
            article['scout_comments'] = "スカウトコメント候補なし"
            print(f"[DEBUG] スカウトコメント候補なし、AI処理スキップ: {article.get('title', '')[:50]}...")
        
        article['scout_rows'] = scout_rows  # ← 各記事ごとにセット
        processed_articles.append(article)
    
    print(f"[DEBUG] has_scout_comment_candidate=True の記事数: {keyword_count}")
    return processed_articles 


def process_player_candidates_with_ai(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    選手候補記事にAI抽出を適用し、article['player_candidate_rows']へ格納する。
    """
    processed_articles = []
    candidate_count = 0

    for article in articles:
        player_candidate_rows: List[Dict[str, Any]] = []

        if article.get('has_player_candidate', False):
            candidate_count += 1
            try:
                full_text = f"{article.get('title', '')}\n\n{article.get('body', '')}"
                print(f"[DEBUG] 選手候補AI処理実行: {article.get('title', '')[:50]}...")
                extracted = extract_player_candidates_with_gemini(
                    full_text,
                    article.get('title', ''),
                    article.get('date', ''),
                    article.get('url', ''),
                )

                for item in extracted:
                    name = (item.get('name') or '').strip()
                    if not name or name in ('不明', 'unknown', 'Unknown'):
                        continue
                    player_candidate_rows.append({
                        'name': name,
                        'name_kana': item.get('name_kana'),
                        'team_name': item.get('team_name'),
                        'team': item.get('team') or item.get('team_name'),
                        'category': item.get('category'),
                        'draft_year': item.get('draft_year'),
                        'school_year': item.get('school_year'),
                        'positions': item.get('positions') or [],
                        'position': item.get('position'),
                        'throws': item.get('throws'),
                        'bats': item.get('bats'),
                        'height_cm': item.get('height_cm'),
                        'weight_kg': item.get('weight_kg'),
                        'birth_date': item.get('birth_date'),
                        'fastball_max': item.get('fastball_max'),
                        'description': item.get('description'),
                        'source_url': article.get('url', ''),
                        'source_title': article.get('title', ''),
                        'published_at': article.get('date', ''),
                        'source': article.get('source', ''),
                        'article_category': article.get('category', ''),
                        'evidence': item.get('evidence'),
                        'confidence': item.get('confidence'),
                        'extracted_raw': item,
                    })
            except Exception as e:
                print(f"[エラー] 選手候補AI処理失敗: {article.get('title', '')} - {e}")
        else:
            print(f"[DEBUG] 選手候補なし、AI処理スキップ: {article.get('title', '')[:50]}...")

        article['player_candidate_rows'] = player_candidate_rows
        processed_articles.append(article)

    print(f"[DEBUG] has_player_candidate=True の記事数: {candidate_count}")
    return processed_articles


def process_scout_visits_with_ai(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    視察情報候補記事にAI抽出を適用し、article['scout_visit_rows']へ格納する。
    """
    processed_articles = []
    visit_candidate_count = 0

    for article in articles:
        scout_visit_rows: List[Dict[str, Any]] = []

        if article.get('has_attention_candidate', False):
            visit_candidate_count += 1
            try:
                full_text = f"{article.get('title', '')}\n\n{article.get('body', '')}"
                print(f"[DEBUG] 視察情報AI処理実行: {article.get('title', '')[:50]}...")
                extracted = extract_scout_visits_with_gemini(
                    full_text,
                    article.get('title', ''),
                    article.get('date', ''),
                    article.get('url', ''),
                )

                named_items = []
                all_teams_items = []
                for item in extracted:
                    player_name = (item.get('player_name') or '').strip()
                    if not player_name or player_name in ('不明', 'unknown', 'Unknown'):
                        continue
                    team_name = (item.get('team_name') or '').strip() or None
                    if not team_name and item.get('is_all_npb_teams'):
                        all_teams_items.append((player_name, item))
                    else:
                        named_items.append((player_name, team_name, item))

                def _build_base_row(player_name, item):
                    return {
                        'player_name': player_name,
                        'person_count': item.get('person_count'),
                        'event_date_text': item.get('event_date_text'),
                        'event_date': item.get('event_date'),
                        'event_date_precision': item.get('event_date_precision'),
                        'source_url': article.get('url', ''),
                        'source_title': article.get('title', ''),
                        'published_at': article.get('date', ''),
                        'source': article.get('source', ''),
                        'article_category': article.get('category', ''),
                        'evidence': item.get('evidence'),
                        'extracted_raw': item,
                    }

                # 個別球団名が判明している視察情報を先に確定する
                named_team_keys_by_player: Dict[str, set] = {}
                for player_name, team_name, item in named_items:
                    team_key = normalize_team_key(team_name)
                    named_team_keys_by_player.setdefault(player_name, set())
                    if team_key:
                        named_team_keys_by_player[player_name].add(team_key)
                    row = _build_base_row(player_name, item)
                    row['team_name'] = team_name
                    row['team_key'] = team_key
                    scout_visit_rows.append(row)

                # 「NPB全12球団が視察」は、個別に名前が挙がっている球団を除いて確定情報として展開する
                for player_name, item in all_teams_items:
                    already_named = named_team_keys_by_player.get(player_name, set())
                    for all_team_key in ALL_NPB_TEAM_KEYS:
                        if all_team_key in already_named:
                            continue
                        row = _build_base_row(player_name, item)
                        row['team_name'] = None
                        row['team_key'] = all_team_key
                        scout_visit_rows.append(row)
            except Exception as e:
                print(f"[エラー] 視察情報AI処理失敗: {article.get('title', '')} - {e}")
        else:
            print(f"[DEBUG] 視察情報候補なし、AI処理スキップ: {article.get('title', '')[:50]}...")

        article['scout_visit_rows'] = scout_visit_rows
        processed_articles.append(article)

    print(f"[DEBUG] has_attention_candidate=True の記事数: {visit_candidate_count}")
    return processed_articles


def generate_draft_watch_article_with_gemini(summary_json: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    summary_json（複数ソースから整理済みの構造化データ）からDraft-Watch下書き記事を生成する。
    外部記事の言い換えではなく、固定テンプレート（タイトル/リード文/本記/評価ポイント/見どころ/出典一覧）に
    沿った独自記事として生成する。
    """
    try:
        model = setup_gemini()

        prompt = f"""
あなたはプロ野球ドラフト専門メディア「Draft-Watch」の記者AIです。
以下の構造化データ（複数の外部記事から整理済みの素材）をもとに、Draft-Watch独自の下書き記事を作成してください。

【厳守事項】
- 外部記事の文章をそのまま転載・言い換えしない。素材を整理し直した独自の記事にする。
- 構造化データに含まれない情報を推測・創作しない（不明な点は無理に書かない）。
- 記事は必ず Markdown の見出し（##）を使って構造化する。プレーンテキストの段落だけを並べてはいけない。
  ドラフト専門メディアでよく見られる、次の構成・文体を踏襲する:

  1. リード文（100〜150字程度、1段落）
     - 見出しは付けず、記事冒頭の導入文として置く。
     - 「誰が」「いつ・どこで」「何をしたか」を、具体的な数値（球速・成績・視察球団数など）を交えて簡潔に要約する。
     - この一段落で記事の主題が伝わるようにする。

  2. 本記（内容のまとまりごとに `## 中見出し` を付け、2〜3個のセクションに分ける）
     - 見出しは「本記」「リード文」のような形式名ではなく、内容を表す具体的な小見出しにする
       （例: 「## 11球団のスカウトが視察」「## 高校通算16本塁打の打撃力」「## 夏へ向けた成長」）。
     - 各セクションは150〜400字程度。topic_typeに応じて以下の展開順序を選ぶ:
       - 試合・プレー中心の話題（player_watchなど）の場合:
         出来事の詳細描写（試合状況・投球内容・打撃内容など）
         → 当該選手の対応や活躍ぶりの描写
         → 本人のコメント（あれば「」で引用）
         → スカウト・球団の視察・評価情報
         → 経歴や成長過程（出身校・入団後の変化など、データにあるもののみ）
         → 今後の目標や課題
       - スカウト会議・候補リストアップ系の話題（scout_meetingなど）の場合:
         会議や発表が行われた事実（いつ・どこで・誰が）
         → 候補者数の絞り込みなど数値的な変化
         → 上位候補として名前が挙がった選手の具体的な列挙（高校生・大学生・社会人などで層別できる場合は層別する。箇条書き `-` を使ってよい）
         → 球団側の新方針や戦略についての言及
     - いずれの場合も、データにある事実を時系列・論理順に並べ、推測で繋がない。

  3. コメント・評価の引用ルール（本記の各セクション内で使う）
     - 関係者やスカウトのコメントは「」で囲み、文末に（媒体名）の形で出典を明記する（例: 「～と話す」（スポーツニッポン））。
     - 引用元はsummary_json中のscout_commentsやeventsなど、構造化データにある発言・出典のみを使う。創作した発言を「」に入れない。
     - 文体は「～と話す」「～と振り返る」「～と指摘した」「～との評価を得ている」「～と見られる」など、関係者の声や評価を一歩引いた立場で紹介する表現を使う。
     - 評価表現は「世代屈指の剛腕」「本格派右腕」のように簡潔で具体的なものを、データに基づく範囲で用いる。

  4. 結び（`## 今後の見どころ` など内容に応じた見出しを付けた1段落）
     - 断定的な評論で締めくくらず、今後の展開を示唆する書き方にする。
     - 「～ことになりそうだ」「～注目が集まる」のように期待・予測を示す形、または会議・視察の事実を淡々と提示して読者の関心を持続させる形のどちらかを、データの性質に合わせて選ぶ。

  5. 出典一覧（`## 出典` という見出しを付ける）
     - その下に summary_json の sources 配列の要素「だけ」を「- [媒体名] タイトル」の形式で列挙する。
     - sources に含まれない情報（eventsの本文や推測など）を出典として加えない。sources が1件なら出典も1行にする。

  全体の文体は「～した」「～見せた」のような過去形・進行形を基本とし、数値は「156キロ」のように算用数字、球団数など概数的な表現は「9球団」のように漢数字も使い分ける。

【出力形式】
JSONオブジェクトのみを返してください。説明文、Markdownのコードブロック、前置きは不要です。
キー:
- title: 記事タイトル。ドラフト専門メディアで実際によく使われる、次のスタイルに沿って作る。
  - 冒頭に【カテゴリ】タグを付ける（例: 【高校野球】【大学野球】【社会人野球】【スカウト会議】【ドラフト】など。summary_jsonのtopic_type・main_player.team・eventsの内容から最も適切なものを選ぶ）
  - 「所属（学校・チーム名）＋選手名＋ポジション」を主語に、「何が起きたか」を具体的な動詞で表す（好投・好打・視察集中・スカウト会議での評価 など）
  - summary_jsonにある具体的な数値（球速、成績、視察球団数・人数など）を積極的に盛り込み、説得力を持たせる。数値が無い場合は創作しない
  - 「怪物」「熱視線」「驚愕」のように、内容に見合った範囲で読者の関心を引く一語を添えてもよい（事実と異なる誇張は禁止）
  - 文末は「〜へ」「〜など注目」のように今後への期待を残す形で締めてもよい
  - 全体で50〜90字程度を目安にする（一目で主題と数値的根拠が伝わる長さにする）
- markdown: 上記構成に沿った本文（Markdown形式の文字列。タイトルの見出し行は含めない）

【構造化データ】
{json.dumps(summary_json, ensure_ascii=False, indent=2)}
"""
        response = model.generate_content(prompt)
        parsed = _parse_json_object(response.text)
        if not parsed:
            return None

        title = str(parsed.get('title') or '').strip()
        markdown = str(parsed.get('markdown') or '').strip()
        if not title or not markdown:
            return None

        return {'title': title, 'markdown': markdown}

    except Exception as e:
        print(f"[Generative AI Gemini Draft-Watch記事生成エラー] {e}")
        return None
