"""
汎用ユーティリティ関数
"""

import re
import unicodedata
from typing import List, Dict, Any, Optional
from datetime import datetime

import hashlib
from difflib import SequenceMatcher

# 旧字体・異体字 → 新字体（NFKCでは統一されないため明示変換する）。
# 氏名・学校名の名寄せ（百合澤↔百合沢、國學院↔国学院 等）に使う。
KYUJITAI_MAP = str.maketrans({
    '澤': '沢', '邊': '辺', '邉': '辺', '髙': '高', '齋': '斎', '齊': '斉',
    '國': '国', '學': '学', '濱': '浜', '廣': '広', '德': '徳', '瀨': '瀬',
    '圓': '円', '萬': '万', '惠': '恵', '槇': '槙', '﨑': '崎', '嶋': '島',
    '眞': '真', '會': '会', '櫻': '桜', '澁': '渋', '彅': '薙',
})


def _to_shinjitai(text: str) -> str:
    """NFKC正規化 + 旧字体→新字体変換。"""
    if not text:
        return text
    return unicodedata.normalize('NFKC', text).translate(KYUJITAI_MAP)


# 学校名の略称・別表記 → 正式名（サフィックス正規化「大学→大」を施した後の形で定義）。
# 観測された表記ゆれを中心に少数を手当てする（必要に応じて追記）。
SCHOOL_ALIAS = {
    '慶大': '慶應義塾大',
    '関大': '関西大',
    '大商大': '大阪商業大',
    '北九州市大': '北九州市立大',
    '日体大': '日本体育大',
    '東日本国際大': '東日本国際大',
    '近大': '近畿大',
    '中大': '中央大',
    '法大': '法政大',
    '明大': '明治大',
    '立大': '立教大',
    '専大': '専修大',
    '駒大': '駒澤大',
    '東洋大': '東洋大',
    '亜大': '亜細亜大',
    '国学院大': '国学院大',
}


def normalize_comment_text(comment: Optional[str]) -> str:
    """
    スカウトコメントの表記を統一する。
    - 前後の鉤括弧・引用符（「」『』""''）を除去（鉤括弧の有無を統一）
    - 前後空白の除去・連続空白の単一化
    Yahoo等の転載と元記事で「」有無だけ違うコメントを同一視できるようにする目的も兼ねる。
    """
    if not comment:
        return ''
    text = comment.strip()
    text = re.sub(r'^[「『“”"\'\s]+', '', text)
    text = re.sub(r'[」』“”"\'\s]+$', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def comment_dedup_key(comment: Optional[str]) -> str:
    """重複判定用にコメントを正規化した小文字キー（鉤括弧・空白を無視）。"""
    return normalize_comment_text(comment).lower()


def loose_comment_key(comment: Optional[str]) -> str:
    """
    緩い重複判定キー。句読点・記号・空白・鉤括弧をすべて除去し、文字（かな漢字英数）だけ残す。
    末尾の「。」有無やYahoo転載時の体裁差で取りこぼさないようにする目的。
    """
    text = normalize_comment_text(comment).lower()
    # 文字・数字（CJK含む）以外（句読点・記号・空白）をすべて除去。
    return re.sub(r'[^0-9a-z぀-ヿ㐀-鿿ｦ-ﾟ]', '', text)


def normalize_school_key(team_name: Optional[str]) -> Optional[str]:
    """
    学校・所属名を名寄せ用の決定的キーへ正規化する。
    旧字体変換 → 空白除去 → サフィックス正規化（大学→大 / 高等学校・高校→高）→ 略称マップ。
    例: 関西大学/関西大/関大 → 'かんさい…' ではなく '関西大'、慶應義塾大学/慶大 → '慶應義塾大'。
    """
    if not team_name:
        return None
    text = _to_shinjitai(team_name).strip()
    text = re.sub(r'\s+', '', text)
    if not text:
        return None
    # サフィックス正規化（長い表記から）。
    text = re.sub(r'大學$', '大', text)
    text = re.sub(r'大学$', '大', text)
    text = re.sub(r'(高等学校|高校)$', '高', text)
    # 略称・別表記を正式名へ寄せる。
    text = SCHOOL_ALIAS.get(text, text)
    return text.lower() or None

def contains_keywords(text: str, keywords: List[str]) -> bool:
    """
    テキストにキーワードが含まれているかチェック
    """
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)

SCOUT_COMMENT_ROLE_PATTERN = re.compile(
    r'(スカウト[\w一-龥ァ-ンー・／兼]*|アマスカウト[\w一-龥ァ-ンー・／兼]*|'
    r'編成(?:[\w一-龥ァ-ンー・／兼]{0,16})?(?:本部長|副本部長|部長|副部長|担当|ディレクター|部|グループ)|'
    r'球団本部[\w一-龥ァ-ンー・／兼]*|'
    r'統括[\w一-龥ァ-ンー・／兼]*|育成Gマネージャー|スカウトGマネージャー|'
    r'スカウトGディレクター|アマスカウトGディレクター|'
    r'(?:GM|ＧＭ)(?!業)|CBO|ＣＢＯ|ゼネラルマネジャー|球団関係者|'
    r'MLBスカウト|メジャースカウト)'
)
SCOUT_AFFILIATED_ROLE_PATTERN = re.compile(
    r'(チーフ|チーフ補佐|投手チーフ|グループ長|ディレクター|'
    r'スーパーバイザー|アドバイザー|顧問|参与|主任|補佐|デスク|'
    r'本部長|副本部長|部長|副部長|マネージャー)'
)
SCOUT_COMMENT_VERB_PATTERN = re.compile(
    r'(評価|絶賛|太鼓判|コメント|話した|語った|評した|称賛|注目|マーク)'
)
NEGATIVE_SIGNAL_PATTERN = re.compile(
    r'(コメントはなかった|コメントはない|コメントなし|発言はなかった|発言はない|'
    r'視察の記述はない|視察の記述はなかった|視察はなかった|視察はない|'
    r'スカウトの具体的なコメントはなかった|具体的なコメントはなかった|'
    r'7回制|７回制|7イニング制|７イニング制|意見交換会|検討会議|'
    r'野球事業|取締役|新球団名|独立リーグ)'
)
ATTENTION_PATTERN = re.compile(
    r'(視察|集結|熱視線|スカウト陣|スカウトが訪れ|スカウト.*詰めかけ|'
    r'スカウト.*見守|スカウト.*持参|バックネット裏.*スカウト|'
    # 「見守った…スカウト」「ネット裏…スカウト」のように語順が逆のケースも拾う（同一文内）。
    r'見守[^。\n]{0,40}スカウト|ネット裏[^。\n]{0,40}スカウト|スカウト[^。\n]{0,40}ネット裏|'
    r'\d+球団|[０-９]+球団|[一二三四五六七八九十十一十二]+球団|'
    r'全球団|12球団|十二球団|日米\d+球団|日米[０-９]+球団|'
    r'MLBスカウト|メジャースカウト|メジャー.*スカウト|米球団)'
)
PLAYER_CANDIDATE_PATTERN = re.compile(
    r'(プロ注目|今秋(?:の)?ドラフト|ドラフト候補|ドラフト上位候補|上位候補|'
    r'1位候補|１位候補|指名候補|リストアップ|スカウト視察|'
    r'最速(?:15[0-9]|１[５-９][０-９])キロ|最速(?:15[0-9]|１[５-９][０-９])km)'
)
JAPANESE_TEAM_NAMES = [
    '巨人', '阪神', '中日', '広島', 'DeNA', '横浜DeNA', 'ヤクルト',
    '西武', '日本ハム', 'ロッテ', 'ソフトバンク', 'オリックス', '楽天'
]

TEAM_NAME_TO_KEY = {
    '巨人': 'giants',
    '読売': 'giants',
    '読売ジャイアンツ': 'giants',
    '読売巨人軍': 'giants',
    '阪神': 'tigers',
    '阪神タイガース': 'tigers',
    '中日': 'dragons',
    '中日ドラゴンズ': 'dragons',
    '広島': 'carp',
    '広島東洋カープ': 'carp',
    'DeNA': 'baystars',
    '横浜DeNA': 'baystars',
    '横浜ＤｅＮＡ': 'baystars',
    '横浜DeNAベイスターズ': 'baystars',
    '横浜ＤｅＮＡベイスターズ': 'baystars',
    'ヤクルト': 'swallows',
    '東京ヤクルトスワローズ': 'swallows',
    '西武': 'lions',
    '埼玉西武ライオンズ': 'lions',
    '日本ハム': 'fighters',
    '日ハム': 'fighters',
    '北海道日本ハムファイターズ': 'fighters',
    'ロッテ': 'marines',
    '千葉ロッテマリーンズ': 'marines',
    'ソフトバンク': 'hawks',
    'ソフトB': 'hawks',
    '福岡ソフトバンク': 'hawks',
    '福岡ソフトバンクホークス': 'hawks',
    'オリックス': 'buffaloes',
    'オリックス・バファローズ': 'buffaloes',
    'オリックスバファローズ': 'buffaloes',
    '楽天': 'eagles',
    '東北楽天': 'eagles',
    '東北楽天ゴールデンイーグルス': 'eagles',
}

# NPB12球団のteam_key一覧（「全12球団が視察」のような記述を全球団確定情報として展開する際に使用）
ALL_NPB_TEAM_KEYS = [
    'giants', 'tigers', 'dragons', 'carp', 'baystars', 'swallows',
    'lions', 'fighters', 'marines', 'hawks', 'buffaloes', 'eagles',
]


def normalize_team_key(team_name: Optional[str]) -> Optional[str]:
    """
    記事中の球団表記をDraft-Watchサイトの team_key（giants, hawksなど）へ変換する。
    対応表にない表記は None を返す。
    """
    if not team_name:
        return None
    name = team_name.strip()
    if name in TEAM_NAME_TO_KEY:
        return TEAM_NAME_TO_KEY[name]
    # 対応表にない表記ゆれ（正式名称の一部表記など）を部分一致で救済する。
    # 長い表記から優先することで「巨人」より「読売ジャイアンツ」を優先的にマッチさせる。
    for known_name in sorted(TEAM_NAME_TO_KEY, key=len, reverse=True):
        if known_name in name:
            return TEAM_NAME_TO_KEY[known_name]
    return None


def normalize_player_key(name: Optional[str]) -> Optional[str]:
    """
    選手名をtopic_key用の決定的なキーへ正規化する
    （全角半角・スペース・敬称を除去した小文字キー）。
    """
    if not name:
        return None
    # 旧字体・異体字を新字体へ寄せて表記ゆれを吸収（百合澤↔百合沢、高橋↔髙橋 等）。
    text = _to_shinjitai(name).strip().replace('　', ' ')
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'(選手|くん|君|さん)$', '', text)
    return text.lower() or None


def build_topic_key(
    topic_type: str,
    *,
    draft_year: Optional[int] = None,
    player_key: Optional[str] = None,
    event_date: Optional[str] = None,
    team: Optional[str] = None,
    meeting_date: Optional[str] = None,
    game_date: Optional[str] = None,
    team_a: Optional[str] = None,
    team_b: Optional[str] = None,
    category: Optional[str] = None,
    theme: Optional[str] = None,
    title_hash: Optional[str] = None,
) -> Optional[str]:
    """
    docs/data_pipeline_strategy.md の「トピックの単位とtopic_key」の形式で決定的なキーを生成する。
    必要な要素が欠けている場合は None を返す（呼び出し側で topic_type=other にフォールバックする）。
    """
    if topic_type == 'player_watch':
        if not player_key or not event_date:
            return None
        return f"player_watch:{draft_year or 'unknown'}:{player_key}:{event_date}"
    if topic_type == 'scout_meeting':
        if not team or not meeting_date:
            return None
        return f"scout_meeting:{team}:{meeting_date}:{draft_year or 'unknown'}"
    if topic_type == 'game_report':
        if not game_date or not team_a or not team_b:
            return None
        team_a_key, team_b_key = sorted([team_a, team_b])
        return f"game_report:{game_date}:{team_a_key}:{team_b_key}"
    if topic_type == 'ranking':
        if not category or not theme:
            return None
        return f"ranking:{draft_year or 'unknown'}:{category}:{theme}"
    if topic_type == 'other':
        if not title_hash:
            return None
        return f"other:{title_hash}"
    return None


SCOUT_MEETING_KEYWORDS = [
    'スカウト会議', '編成会議', 'ドラフト会議へ向け', 'リストアップ',
    '上位候補', '1位候補', '指名候補', '候補選手を確認', '球団幹部',
]


def has_scout_meeting_signal(text: str) -> bool:
    """
    スカウト会議・編成会議系の記事を検出する（Draft-Watch記事化候補のtopic_type判定に使用）。
    """
    if not text:
        return False
    return any(keyword in text for keyword in SCOUT_MEETING_KEYWORDS)


KNOWN_SCOUT_STAFF_NAMES = [
    '福澤洋一', '木塚敦志', '宮田善久', '山本省吾', '河野亮', '近藤弘樹',
    '岡野祐一郎', '斉藤宜之', '上村和裕', '大本将吾', '小川淳司', '森中聖雄',
    '末永真史', '大久保勝也', '岸敬祐', '武田康', '藤田和男', '丸山泰嗣',
    '足立祐一', '高橋憲幸', '三瀬幸司', '縞田拓弥', '後関昌彦', '有吉優樹',
    '栗山英樹', '白井康勝', '苑田聡彦', '井上純', '田村恵', '水澤英樹',
    '下山真二', '岩見雅紀', '長谷川竜也', '松本有史', '松岡健一', '永池恭男',
    '阿部真宏', '河原隆一', '木村龍治', '吉野誠', '山本将道', '野本圭',
    '篠原貴行', '加藤領健', '鞘師智也', '黒木純司', '萩田圭', '松本輝',
    '前田俊郎', '横山道哉', '東辰弥', '榑松伸介', '山口和男', '前田忠節',
    '山本一徳', '岡本洋介', '田中良平', '渡辺政仁', '平岡佑梧', '竹下潤',
    '松田慎司', '石本努', '安達俊也', '柳沼強', '伊東昭光', '齊藤誠人',
    '小松聖', '柳舘俊', '小川一夫', '大場豊千', '熊崎誠也', '岡崎大輔',
    '作山和英', '小林敦', '稲嶺誉', '愛敬尚史', '鈴木敬洋', '稲嶺茂夫',
    '牧田勝吾', '織田淳哉', '松本尚樹', '小山良男', '早川大輔', '山本宣史',
    '青木宣親', '筒井和也', '葛西稔', '沖原佳典', '近藤芳久', '安藤強',
    '部坂俊之', '円谷英俊', '高木康成', '山田潤', '加藤竜人', '榎康弘',
    '水野雄仁', '菅野剛士', '松永幸男', '八木智哉', '平塚克洋', '音重鎮',
    '柏田貴史', '清水昭信', '福山龍太郎', '上本達之', '高山健一', '畑山俊二',
    '押尾健一', '後藤光貴', '十亀剣', '正津英志', '八馬幹典', '尾形佳紀',
    '余田雄飛', '古澤勝吾', '橿渕聡', '青木高広', '中川隆治', '福元淳史',
    '木佐貫洋', '岳野竜也', '山田正雄', '伊藤剛', '阿部健太', '竹内孝行',
    '永井智浩', '白武佳久', '坂本晃一', '鈴木宏昌アントニー', '三家和真',
    '大渕隆', '益田大介'
]
KNOWN_SCOUT_STAFF_SURNAMES = sorted(
    {re.sub(r'\s+', '', name)[:2] for name in KNOWN_SCOUT_STAFF_NAMES if len(re.sub(r'\s+', '', name)) >= 2},
    key=len,
    reverse=True
)

KANJI_NUMBERS = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
    '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12
}


def _normalize_number(value: str) -> Optional[int]:
    value = value.strip()
    value = value.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    if value.isdigit():
        return int(value)
    return KANJI_NUMBERS.get(value)


def _normalize_person_text(text: str) -> str:
    return re.sub(r'\s+', '', text)


def _has_known_scout_staff(text: str) -> bool:
    normalized = _normalize_person_text(text)
    for name in KNOWN_SCOUT_STAFF_NAMES:
        if name in normalized:
            return True

    return False


def _is_negative_signal(text: str) -> bool:
    return bool(NEGATIVE_SIGNAL_PATTERN.search(text))


def _has_former_role_prefix(text: str, role_start: int) -> bool:
    prefix = text[max(0, role_start - 10):role_start]
    return bool(re.search(r'(元|前)[^。\n]{0,9}$', prefix))


def _is_attention_signal_sentence(sentence: str) -> bool:
    if not ATTENTION_PATTERN.search(sentence):
        return False
    if re.search(r'(セカンドキャリア|戦力外|引退後|進路調査|ジュニアトーナメント|特別企画|メンバー表|本塁打数)', sentence):
        return False
    if '集結' in sentence and not re.search(r'(スカウト|球団|NPB|ＮＰＢ|日米|米球団)', sentence):
        return False
    if '全球団' in sentence and not re.search(r'(スカウト|視察|熱視線|ドラフト|候補|プロ注目|オファー|獲得調査|リストアップ|訪れ|見守|持参|バックネット|態勢)', sentence):
        return False
    if re.search(r'([0-9０-９]+|[一二三四五六七八九十十一十二]+|全球団|12|１２|十二)球団', sentence):
        if not re.search(r'(スカウト|視察|熱視線|ドラフト|候補|プロ注目|オファー|獲得調査|リストアップ|訪れ|見守|持参|バックネット|態勢)', sentence):
            return False
    return True


def has_scout_comment_candidate(text: str) -> bool:
    """
    スカウト・編成・GM系の選手評価コメントがありそうな記事か判定する。
    監督・コーチ単独のコメントはここでは候補にしない。
    """
    if not text:
        return False
    if re.search(r'(7回制|７回制|7イニング制|７イニング制|意見交換会|検討会議)', text):
        return False

    for role_match in SCOUT_COMMENT_ROLE_PATTERN.finditer(text):
        if _has_former_role_prefix(text, role_match.start()):
            continue
        window = text[role_match.start():role_match.start() + 400]
        if (
            not _is_negative_signal(window)
            and SCOUT_COMMENT_VERB_PATTERN.search(window)
            and ('スカウト' in role_match.group(0) or '「' in window[:220])
        ):
            return True

    normalized_text = _normalize_person_text(text)
    for name in KNOWN_SCOUT_STAFF_NAMES:
        pos = normalized_text.find(name)
        if pos >= 0:
            window = normalized_text[pos:pos + 400]
            if (
                not _is_negative_signal(window)
                and
                (SCOUT_COMMENT_ROLE_PATTERN.search(window) or SCOUT_AFFILIATED_ROLE_PATTERN.search(window))
                and SCOUT_COMMENT_VERB_PATTERN.search(window)
            ):
                return True

    for sentence in re.split(r'[。\n]', text):
        if _has_known_scout_staff(sentence) and SCOUT_AFFILIATED_ROLE_PATTERN.search(sentence):
            window_start = text.find(sentence)
            window = text[window_start:window_start + 400] if window_start >= 0 else sentence
            if not _is_negative_signal(window) and SCOUT_COMMENT_VERB_PATTERN.search(window):
                return True

    for sentence in re.split(r'[。\n]', text):
        role_match = SCOUT_COMMENT_ROLE_PATTERN.search(sentence)
        if (
            not _is_negative_signal(sentence)
            and role_match
            and not _has_former_role_prefix(sentence, role_match.start())
            and SCOUT_COMMENT_VERB_PATTERN.search(sentence)
        ):
            return True
    return False


def has_attention_candidate(text: str) -> bool:
    """
    視察球団数・視察人数・球団名など、注目度情報がありそうな記事か判定する。
    """
    if not text:
        return False

    for sentence in re.split(r'[。\n]', text):
        if _is_attention_signal_sentence(sentence) and not _is_negative_signal(sentence):
            return True
    return False


def has_player_candidate(text: str) -> bool:
    """
    選手候補抽出AIに回す価値がありそうな記事か判定する。
    """
    if not text:
        return False

    if PLAYER_CANDIDATE_PATTERN.search(text):
        return True

    return has_attention_candidate(text) or has_scout_comment_candidate(text)


def calculate_attention_score(team_count: int, person_count: int, team_keys: List[str], has_mlb: bool, has_comment_candidate: bool) -> int:
    score = 0
    if team_count >= 12:
        score = 5
    elif team_count >= 8:
        score = 4
    elif team_count >= 5:
        score = 3
    elif team_count >= 2:
        score = 2
    elif team_keys:
        score = 2
    elif person_count > 0:
        score = 1

    if person_count >= 10:
        score += 1
    if has_mlb:
        score += 1
    if has_comment_candidate:
        score += 1

    return min(score, 7)


def _extract_scout_person_count(sentence: str) -> int:
    patterns = [
        r'([0-9０-９]+|[一二三四五六七八九十十一十二]+)人(?:の)?スカウト',
        r'スカウト(?:陣)?([0-9０-９]+|[一二三四五六七八九十十一十二]+)人',
        r'([0-9０-９]+|[一二三四五六七八九十十一十二]+)人(?:態勢|で視察|が視察|が集結|が見守)',
    ]
    for pattern in patterns:
        match = re.search(pattern, sentence)
        if match:
            return _normalize_number(match.group(1)) or 0
    return 0


def extract_attention_rows(article: Dict[str, Any]) -> List[List[Any]]:
    """
    記事から視察球団数・人数・球団名・注目度をルールベースで抽出する。
    """
    body = article.get('body', '') or ''
    title = article.get('title', '') or ''
    texts = [body] if body else []
    if not texts:
        texts.append(title)
    rows = []

    for text in texts:
        for sentence in re.split(r'[。\n]', text):
            sentence = clean_text(sentence)
            if not sentence or not _is_attention_signal_sentence(sentence):
                continue
            if _is_negative_signal(sentence):
                continue

            team_count = 0
            person_count = 0

            if re.search(r'(全球団|12球団|十二球団)', sentence):
                team_count = 12
            else:
                team_count_match = re.search(r'([0-9０-９]+|[一二三四五六七八九十十一十二]+)球団', sentence)
                if team_count_match:
                    team_count = _normalize_number(team_count_match.group(1)) or 0

            person_count = _extract_scout_person_count(sentence)

            team_keys = []
            for team in JAPANESE_TEAM_NAMES:
                if team in sentence:
                    team_key = normalize_team_key(team)
                    if team_key and team_key not in team_keys:
                        team_keys.append(team_key)

            has_mlb = bool(re.search(r'(MLB|ＭＬＢ|メジャー|大リーグ|日米)', sentence))
            has_npb = bool(re.search(r'(NPB|ＮＰＢ|プロ野球|球団|スカウト|視察)', sentence)) or bool(team_keys)
            has_comment = has_scout_comment_candidate(sentence)
            has_scout_presence = bool(re.search(r'スカウト', sentence))

            if not (team_count or person_count or team_keys or has_mlb or has_comment or has_scout_presence):
                continue

            score = calculate_attention_score(team_count, person_count, team_keys, has_mlb, has_comment)
            if score == 0 and has_scout_presence:
                score = 1
            rows.append([
                article.get('date', ''),
                article.get('source', ''),
                article.get('category', ''),
                article.get('title', ''),
                article.get('url', ''),
                team_count,
                person_count,
                ', '.join(team_keys),
                'TRUE' if has_npb else 'FALSE',
                'TRUE' if has_mlb else 'FALSE',
                score,
                sentence
            ])

    return rows


def annotate_article_signals(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    記事にスカウトコメント候補・視察注目度候補・注目度行を付与する。
    has_keywordsは既存処理互換のため、どちらかの候補があればTrueにする。
    """
    text = f"{article.get('title', '')}\n\n{article.get('body', '')}"
    scout_candidate = has_scout_comment_candidate(text)
    attention_candidate = has_attention_candidate(text)
    player_candidate = has_player_candidate(text)
    article['has_scout_comment_candidate'] = scout_candidate
    article['has_attention_candidate'] = attention_candidate
    article['has_player_candidate'] = player_candidate
    article['has_keywords'] = scout_candidate or attention_candidate
    article['attention_rows'] = extract_attention_rows(article) if attention_candidate else []
    return article

def clean_text(text: str) -> str:
    """
    テキストをクリーニング
    """
    if not text:
        return ""
    
    # 余分な空白を削除
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def format_date_with_time(date_str: str) -> str:
    """
    日付文字列をフォーマット（時間情報付き形式）
    様々な日付形式に対応し、時間情報も含めて統一された形式で出力
    """
    if not date_str:
        return ""
    
    try:
        # 入力文字列をクリーニング
        date_str = date_str.strip()
        
        # 角括弧を除去（スポニチの形式: [ 2025年7月12日 06:00 ]）
        date_str = re.sub(r'^\[|\]$', '', date_str).strip()
        
        # 1. 既にISO 8601形式のタイムスタンプの場合
        iso_pattern = r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})[+-]\d{2}:\d{2}'
        match = re.match(iso_pattern, date_str)
        if match:
            year, month, day, hour, minute, second = match.groups()
            return f"{year}-{month}-{day} {hour}:{minute}"
        
        # 2. 日本語の日付パターン（時間情報付き）
        # 例: "2025年7月12日 06:00" → "2025-07-12 06:00"
        japanese_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s+(\d{1,2})[:時](\d{1,2})[分]?)?'
        match = re.match(japanese_pattern, date_str)
        if match:
            year, month, day, hour, minute = match.groups()
            if hour and minute:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute.zfill(2)}"
            else:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)} 00:00"
        
        # 3. 既にYYYY-MM-DD形式の場合
        if re.match(r'\d{4}-\d{2}-\d{2}$', date_str):
            return f"{date_str} 00:00"
        
        # 4. その他の日付形式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d %H:%M')
            except ValueError:
                continue
        
        # 5. 曜日名を含む場合の処理
        # 例: "2025年7月12日(金)" → "2025-07-12 00:00"
        weekday_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日\([月火水木金土日]\)'
        match = re.match(weekday_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)} 00:00"
        
        # 6. 英語月名を含む場合の処理
        # 例: "July 12, 2025" → "2025-07-12 00:00"
        try:
            from dateutil.parser import parse
            parsed_date = parse(date_str)
            return parsed_date.strftime('%Y-%m-%d %H:%M')
        except:
            pass
        
        # パースできない場合はそのまま返す
        return date_str
    except Exception:
        return date_str

def format_date(date_str: str) -> str:
    """
    日付文字列をフォーマット（YYYY-MM-DD形式）
    様々な日付形式に対応し、統一された形式で出力
    """
    if not date_str:
        return ""
    
    try:
        # 入力文字列をクリーニング
        date_str = date_str.strip()
        
        # 角括弧を除去（スポニチの形式: [ 2025年7月12日 06:00 ]）
        date_str = re.sub(r'^\[|\]$', '', date_str).strip()
        
        # 1. 既にISO 8601形式のタイムスタンプの場合
        iso_pattern = r'(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}'
        match = re.match(iso_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"
        
        # 2. 日本語の日付パターン（時間情報付き）
        # 例: "2025年7月12日 06:00" → "2025-07-12"
        japanese_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s+\d{1,2}[:時]\d{1,2}[分]?)?'
        match = re.match(japanese_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # 3. 既にYYYY-MM-DD形式の場合
        if re.match(r'\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        
        # 4. その他の日付形式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # 5. 曜日名を含む場合の処理
        # 例: "2025年7月12日(金)" → "2025-07-12"
        weekday_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日\([月火水木金土日]\)'
        match = re.match(weekday_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # 6. 英語月名を含む場合の処理
        # 例: "July 12, 2025" → "2025-07-12"
        try:
            from dateutil.parser import parse
            parsed_date = parse(date_str)
            return parsed_date.strftime('%Y-%m-%d')
        except:
            pass
        
        # パースできない場合はそのまま返す
        return date_str
    except Exception:
        return date_str

def format_timestamp(date_str: str) -> str:
    """
    日付文字列をISO 8601形式（timestamp with time zone）にフォーマット
    様々な日付形式に対応し、統一された形式で出力
    """
    if not date_str:
        return ""
    
    try:
        # 入力文字列をクリーニング
        date_str = date_str.strip()
        
        # 角括弧を除去（スポニチの形式: [ 2025年7月12日 06:00 ]）
        date_str = re.sub(r'^\[|\]$', '', date_str).strip()
        
        # 1. 既にISO 8601形式のタイムスタンプの場合
        iso_pattern = r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})[+-]\d{2}:\d{2}'
        match = re.match(iso_pattern, date_str)
        if match:
            year, month, day, hour, minute, second = match.groups()
            return f"{year}-{month}-{day}T{hour}:{minute}:{second}+09:00"
        
        # 2. 日本語の日付パターン（時間情報付き）
        # 例: "2025年7月12日 06:00" → "2025-07-12T06:00:00+09:00"
        japanese_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s+(\d{1,2})[:時](\d{1,2})[分]?)?'
        match = re.match(japanese_pattern, date_str)
        if match:
            year, month, day, hour, minute = match.groups()
            if hour and minute:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}T{hour.zfill(2)}:{minute.zfill(2)}:00+09:00"
            else:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}T00:00:00+09:00"
        
        # 3. 既にYYYY-MM-DD形式の場合
        if re.match(r'\d{4}-\d{2}-\d{2}$', date_str):
            return f"{date_str}T00:00:00+09:00"
        
        # 4. その他の日付形式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # ISO 8601形式で出力（タイムゾーンはJSTとして扱う）
                return parsed_date.strftime('%Y-%m-%dT%H:%M:%S+09:00')
            except ValueError:
                continue
        
        # 5. 曜日名を含む場合の処理
        weekday_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日\([月火水木金土日]\)'
        match = re.match(weekday_pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}T00:00:00+09:00"
        
        # 6. 英語月名を含む場合の処理
        try:
            from dateutil.parser import parse
            parsed_date = parse(date_str)
            return parsed_date.strftime('%Y-%m-%dT%H:%M:%S+09:00')
        except:
            pass
        
        # パースできない場合はそのまま返す
        return date_str
    except Exception:
        return date_str

def calculate_content_hash(title: str, body: str) -> str:
    """
    記事のタイトル+本文からハッシュ値を計算
    """
    # 正規化（空白や改行を統一）
    normalized_title = re.sub(r'\s+', ' ', title.strip())
    normalized_body = re.sub(r'\s+', ' ', body.strip())
    
    # 結合してハッシュ値を計算
    content = f"{normalized_title}\n{normalized_body}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def get_source_priority(source: str) -> int:
    """
    ソースの優先度を取得（数値が小さいほど優先度が高い）
    """
    try:
        # Noneや空文字列の場合はデフォルト値を返す
        if not source:
            return 5
        
        # 文字列でない場合はデフォルト値を返す
        if not isinstance(source, str):
            print(f"[DEBUG] get_source_priority: 非文字列値 detected: {source} (type: {type(source)})")
            return 5
        
        priority_map = {
            # オリジナルソース（既存5社）が最優先
            'スポニチ': 1,
            'スポーツ報知': 1,
            '日刊スポーツ': 1,
            'サンスポ': 1,
            '中日スポーツ': 1,
            
            # Yahoo!スポーツナビは優先度低め
            'Yahoo!スポーツナビ': 10,
            
            # その他は中間
            'その他': 5
        }
        
        result = priority_map.get(source, 5)
        return result
    except Exception as e:
        print(f"[記事更新エラー] get_source_priority エラー: {e}")
        print(f"  入力値: {source} (type: {type(source)})")
        return 5

def are_articles_similar(article1: Dict[str, Any], article2: Dict[str, Any], threshold: float = 0.8) -> bool:
    """
    2つの記事の類似度を判定
    """
    try:
        title1 = article1.get('title', '') or ''
        title2 = article2.get('title', '') or ''
        body1 = article1.get('body', '') or ''
        body2 = article2.get('body', '') or ''
        
        # タイトルの類似度
        title_similarity = SequenceMatcher(None, title1, title2).ratio()
        
        # 本文の類似度
        body_similarity = SequenceMatcher(None, body1, body2).ratio()
        
        # 総合判定（タイトルと本文の両方が高い類似度の場合）
        return title_similarity > threshold and body_similarity > threshold
    except Exception as e:
        print(f"[記事更新エラー] 類似度計算エラー: {e}")
        print(f"  article1: {article1.get('title', '')[:50]}...")
        print(f"  article2: {article2.get('title', '')[:50]}...")
        return False

def deduplicate_articles_advanced(articles: List[Dict[str, Any]], similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    高度な重複除去（URL、タイトル、本文ベース）
    """
    print(f"[DEBUG] 高度な重複除去開始: {len(articles)}件")
    
    # 1. URLベースの重複除去
    seen_urls = set()
    url_unique_articles = []
    
    for article in articles:
        url = article.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            url_unique_articles.append(article)
    
    print(f"[DEBUG] URLベース重複除去後: {len(url_unique_articles)}件")
    
    # 2. ハッシュベースの重複除去
    seen_hashes = {}
    hash_unique_articles = []
    
    for article in url_unique_articles:
        title = article.get('title', '')
        body = article.get('body', '')
        
        # 内容が十分にある記事のみハッシュ化
        if len(title) > 10 and len(body) > 50:
            content_hash = calculate_content_hash(title, body)
            
            if content_hash not in seen_hashes:
                seen_hashes[content_hash] = article
                hash_unique_articles.append(article)
            else:
                # 重複した場合、優先度の高いソースを選択
                existing_article = seen_hashes[content_hash]
                existing_source = existing_article.get('source', '') or ''
                current_source = article.get('source', '') or ''
                
                try:
                    print(f"[DEBUG] ハッシュ重複除去 - 比較開始:")
                    print(f"  existing_article source: {existing_article.get('source')} (type: {type(existing_article.get('source'))})")
                    print(f"  current_article source: {article.get('source')} (type: {type(article.get('source'))})")
                    
                    existing_priority = get_source_priority(existing_source)
                    current_priority = get_source_priority(current_source)
                    
                    print(f"[DEBUG] 優先度比較: {current_priority} < {existing_priority} = {current_priority < existing_priority}")
                    
                    if current_priority < existing_priority:
                        # 現在の記事の方が優先度が高い場合、置き換える
                        seen_hashes[content_hash] = article
                        # リストからも置き換える
                        for i, a in enumerate(hash_unique_articles):
                            if a is existing_article:
                                hash_unique_articles[i] = article
                                break
                    
                    print(f"[DEBUG] ハッシュ重複検出: {title[:50]}... (優先: {article.get('source', '')} vs {existing_article.get('source', '')})")
                except Exception as e:
                    print(f"[記事更新エラー] ハッシュ重複除去エラー: {e}")
                    print(f"  existing_source: {existing_source} (type: {type(existing_source)})")
                    print(f"  current_source: {current_source} (type: {type(current_source)})")
                    print(f"  existing_priority: {existing_priority if 'existing_priority' in locals() else 'undefined'}")
                    print(f"  current_priority: {current_priority if 'current_priority' in locals() else 'undefined'}")
        else:
            # 内容が少ない記事はそのまま追加
            hash_unique_articles.append(article)
    
    print(f"[DEBUG] ハッシュベース重複除去後: {len(hash_unique_articles)}件")
    
    # 3. 類似度ベースの重複除去
    final_articles = []
    
    for article in hash_unique_articles:
        is_duplicate = False
        
        # 既存の記事との類似度をチェック
        for existing_article in final_articles:
            if are_articles_similar(article, existing_article, similarity_threshold):
                # 重複の場合、優先度の高いソースを選択
                existing_source = existing_article.get('source', '') or ''
                current_source = article.get('source', '') or ''
                
                try:
                    print(f"[DEBUG] 類似度重複除去 - 比較開始:")
                    print(f"  existing_article source: {existing_article.get('source')} (type: {type(existing_article.get('source'))})")
                    print(f"  current_article source: {article.get('source')} (type: {type(article.get('source'))})")
                    
                    existing_priority = get_source_priority(existing_source)
                    current_priority = get_source_priority(current_source)
                    
                    print(f"[DEBUG] 優先度比較: {current_priority} < {existing_priority} = {current_priority < existing_priority}")
                    
                    if current_priority < existing_priority:
                        # 現在の記事の方が優先度が高い場合、置き換える
                        for i, a in enumerate(final_articles):
                            if a is existing_article:
                                final_articles[i] = article
                                break
                    
                    print(f"[DEBUG] 類似度重複検出: {article.get('title', '')[:50]}... (優先: {article.get('source', '')} vs {existing_article.get('source', '')})")
                    is_duplicate = True
                    break
                except Exception as e:
                    print(f"[記事更新エラー] 類似度重複除去エラー: {e}")
                    print(f"  existing_source: {existing_source} (type: {type(existing_source)})")
                    print(f"  current_source: {current_source} (type: {type(current_source)})")
                    print(f"  existing_priority: {existing_priority if 'existing_priority' in locals() else 'undefined'}")
                    print(f"  current_priority: {current_priority if 'current_priority' in locals() else 'undefined'}")
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            final_articles.append(article)
    
    print(f"[DEBUG] 最終重複除去後: {len(final_articles)}件")
    
    # 4. 重複除去結果の統計
    sources = {}
    for article in final_articles:
        source = article.get('source', '不明')
        sources[source] = sources.get(source, 0) + 1
    
    print("\n[DEBUG] 重複除去後のソース別記事数:")
    for source, count in sorted(sources.items()):
        print(f"  {source}: {count}件")
    
    return final_articles

def filter_yahoo_unique_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Yahoo!スポーツナビの記事から、既存5社にない独自記事のみを抽出
    """
    yahoo_articles = [a for a in articles if a.get('source') == 'Yahoo!スポーツナビ']
    other_articles = [a for a in articles if a.get('source') != 'Yahoo!スポーツナビ']
    
    print(f"[DEBUG] Yahoo記事数: {len(yahoo_articles)}, その他記事数: {len(other_articles)}")
    
    unique_yahoo_articles = []
    
    for yahoo_article in yahoo_articles:
        is_unique = True
        
        # 既存5社の記事と比較
        for other_article in other_articles:
            if are_articles_similar(yahoo_article, other_article, threshold=0.7):
                print(f"[DEBUG] Yahoo重複除外: {yahoo_article.get('title', '')[:50]}... (重複: {other_article.get('source', '')})")
                is_unique = False
                break
        
        if is_unique:
            unique_yahoo_articles.append(yahoo_article)
    
    print(f"[DEBUG] Yahoo独自記事数: {len(unique_yahoo_articles)}")
    
    # 既存5社の記事 + Yahoo独自記事を結合
    return other_articles + unique_yahoo_articles

def deduplicate_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    記事の重複除去（高度版をデフォルトで使用）
    """
    return deduplicate_articles_advanced(articles) 

def compare_with_existing_articles(articles: List[Dict[str, Any]], similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    既存記事との内容比較のみを行う
    （記事間の重複除去は既に完了している前提）
    """
    print(f"[DEBUG] 既存記事との内容比較開始: {len(articles)}件")
    
    # Google Sheetsから既存記事の内容を取得
    from sheets.google_sheets import get_existing_articles_content, update_existing_article
    
    try:
        existing_articles = get_existing_articles_content()
        print(f"[DEBUG] 既存記事数: {len(existing_articles)}件")
    except Exception as e:
        print(f"[DEBUG] 既存記事取得エラー: {e}")
        existing_articles = []
    
    # 既存記事との内容比較のみ
    final_articles = []
    updated_articles = []  # 更新された記事のリスト
    
    for article in articles:
        is_duplicate_of_existing = False
        
        # 既存記事と類似度をチェック
        for existing_article in existing_articles:
            try:
                if are_articles_similar(article, existing_article, similarity_threshold):
                    # 重複の場合、優先度の高いソースを選択
                    existing_source = existing_article.get('source', '') or ''
                    current_source = article.get('source', '') or ''
                    
                    try:
                        print(f"[DEBUG] 既存記事比較 - 比較開始:")
                        print(f"  existing_article source: {existing_article.get('source')} (type: {type(existing_article.get('source'))})")
                        print(f"  current_article source: {article.get('source')} (type: {type(article.get('source'))})")
                        
                        existing_priority = get_source_priority(existing_source)
                        current_priority = get_source_priority(current_source)
                        
                        print(f"[DEBUG] 優先度比較: {current_priority} < {existing_priority} = {current_priority < existing_priority}")
                        
                        if current_priority < existing_priority:
                            # 新しい記事の方が優先度が高い場合、既存記事を更新
                            existing_url = existing_article.get('url', '')
                            if existing_url:
                                success = update_existing_article(existing_url, article)
                                if success:
                                    updated_articles.append(article)
                                    print(f"[DEBUG] 既存記事を更新: {article.get('title', '')[:50]}... (新: {article.get('source', '')} > 既存: {existing_article.get('source', '')})")
                        else:
                            # 既存記事の方が優先度が高い場合、新しい記事を除外
                            print(f"[DEBUG] 既存記事を優先: {article.get('title', '')[:50]}... (既存: {existing_article.get('source', '')} > 新: {article.get('source', '')})")
                        
                        is_duplicate_of_existing = True
                        break
                    except Exception as e:
                        print(f"[記事更新エラー] 既存記事比較エラー: {e}")
                        print(f"  existing_source: {existing_source} (type: {type(existing_source)})")
                        print(f"  current_source: {current_source} (type: {type(current_source)})")
                        print(f"  existing_priority: {existing_priority if 'existing_priority' in locals() else 'undefined'}")
                        print(f"  current_priority: {current_priority if 'current_priority' in locals() else 'undefined'}")
                        is_duplicate_of_existing = True
                        break
            except Exception as e:
                print(f"[記事更新エラー] 類似度チェックエラー: {e}")
                print(f"  article: {article.get('title', '')[:50]}...")
                print(f"  existing_article: {existing_article.get('title', '')[:50]}...")
                continue
        
        if not is_duplicate_of_existing:
            final_articles.append(article)
    
    print(f"[DEBUG] 既存記事との内容比較後: {len(final_articles)}件（新規）+ {len(updated_articles)}件（更新）")
    
    # 内容比較結果の統計
    all_processed = final_articles + updated_articles
    sources = {}
    for article in all_processed:
        source = article.get('source', '不明')
        sources[source] = sources.get(source, 0) + 1
    
    print("\n[DEBUG] 既存記事との内容比較後のソース別記事数:")
    for source, count in sorted(sources.items()):
        print(f"  {source}: {count}件")
    
    return final_articles  # 新規記事のみを返す（更新された記事は別途処理済み）

def filter_existing_yahoo_urls(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    既存のYahoo!スポーツナビ記事とのURL重複チェック
    URLのみで重複チェックを行い、ハッシュや類似度ベースのチェックは行わない
    """
    print(f"[DEBUG] 既存Yahoo記事URL重複チェック開始: {len(articles)}件")
    
    # 既存のYahoo!スポーツナビ記事のURLを取得（軽量版を使用）
    from sheets.google_sheets import get_existing_urls_by_source, get_existing_urls_lightweight
    
    try:
        # 軽量版を優先使用
        existing_yahoo_urls = get_existing_urls_by_source('Yahoo!スポーツナビ')
        print(f"[DEBUG] 既存Yahoo記事URL数: {len(existing_yahoo_urls)}件")
    except Exception as e:
        print(f"[DEBUG] 既存Yahoo記事URL取得エラー: {e}")
        existing_yahoo_urls = set()
    
    # URL重複チェック
    unique_articles = []
    duplicate_count = 0
    
    for article in articles:
        article_url = article.get('url', '')
        if article_url and article_url not in existing_yahoo_urls:
            unique_articles.append(article)
        elif article_url:
            duplicate_count += 1
            print(f"[DEBUG] 既存Yahoo記事URL重複除外: {article.get('title', '')[:50]}...")
    
    print(f"[DEBUG] 既存Yahoo記事URL重複除外: {duplicate_count}件")
    print(f"[DEBUG] 既存Yahoo記事URL重複チェック後: {len(unique_articles)}件")
    
    return unique_articles

def filter_yahoo_against_existing(yahoo_articles: List[Dict[str, Any]], threshold: float = 0.7) -> List[Dict[str, Any]]:
    """
    Yahoo!スポーツナビの記事から、既存5社の記事と重複しない独自記事のみを抽出
    """
    print(f"[DEBUG] Yahoo独自記事フィルタリング開始: {len(yahoo_articles)}件")
    
    # 既存5社の記事を取得
    from sheets.google_sheets import get_existing_articles_by_source
    
    existing_original_articles = []
    original_sources = ['スポニチ', 'スポーツ報知', '日刊スポーツ', 'サンスポ', '中日スポーツ']
    
    try:
        for source in original_sources:
            source_articles = get_existing_articles_by_source(source)
            existing_original_articles.extend(source_articles)
        
        print(f"[DEBUG] 既存5社の記事数: {len(existing_original_articles)}件")
    except Exception as e:
        print(f"[DEBUG] 既存5社記事取得エラー: {e}")
        existing_original_articles = []
    
    # Yahoo記事と既存5社記事を比較
    unique_yahoo_articles = []
    
    for yahoo_article in yahoo_articles:
        is_unique = True
        
        # 既存5社の記事と比較
        for existing_article in existing_original_articles:
            if are_articles_similar(yahoo_article, existing_article, threshold):
                print(f"[DEBUG] Yahoo重複除外: {yahoo_article.get('title', '')[:50]}... (重複: {existing_article.get('source', '')})")
                is_unique = False
                break
        
        if is_unique:
            unique_yahoo_articles.append(yahoo_article)
    
    print(f"[DEBUG] Yahoo独自記事数: {len(unique_yahoo_articles)}件")
    return unique_yahoo_articles

def smart_deduplicate_articles(
    articles: List[Dict[str, Any]],
    include_existing_comparison: bool = True,
    check_existing_yahoo_urls: bool = False
) -> List[Dict[str, Any]]:
    """
    スマートな重複除去（既存記事との比較オプション付き）
    1. まず記事間の重複除去（URL、ハッシュ、類似度ベース）
    2. 既存Yahoo記事とのURL重複チェック（オプション）
    3. 既存記事との比較（オプション）
    """
    print(f"[DEBUG] スマート重複除去開始: {len(articles)}件")
    
    # 1. まず記事間の重複除去（URL、ハッシュ、類似度ベース）
    deduplicated_articles = deduplicate_articles_advanced(articles)
    print(f"[DEBUG] 記事間重複除去後: {len(deduplicated_articles)}件")
    
    # 2. 既存Yahoo記事とのURL重複チェック
    if check_existing_yahoo_urls:
        deduplicated_articles = filter_existing_yahoo_urls(deduplicated_articles)
        print(f"[DEBUG] 既存Yahoo記事URL重複除去後: {len(deduplicated_articles)}件")
    else:
        print("[DEBUG] 既存Yahoo記事URL重複チェックをスキップ")
    
    # 3. 既存記事との内容比較（オプション）
    if include_existing_comparison:
        print("[DEBUG] 既存記事との内容比較を実行")
        return compare_with_existing_articles(deduplicated_articles)
    else:
        print("[DEBUG] 既存記事との内容比較をスキップ")
        return deduplicated_articles 
