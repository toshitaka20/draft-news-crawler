# 大学リーグ戦の成績の出どころ調査（2026-11-27）

ドラフト候補の成績を「連盟の公式記録を正」として集める仕組みのための下調べ。
対象は draft-watch に登録済みの 2027年以降の大学生 209人（76校）のうち約150人が所属する8連盟。

## 一覧

| 連盟 | 公式サイト | シーズン成績表 | 試合ごとの記録 | 名前の書き方 | 過去分 | 取り方の案 |
|---|---|---|---|---|---|---|
| 東京六大学 | big6.gr.jp | **チーム別に全選手**（打撃・投手） | 選手ごとの試合別成績ページ（playerid付き） | 表は姓だけ、選手ページはフルネーム＋入学年＋出身高校 | あり（2019年も同じURL形式で取れる） | 公式だけで完結 |
| 東都 | tohto-bbl.com | 規定到達者だけ（1〜4部とも） | 試合結果ページに全員の打数・安打・打点、投手の投球回など | 姓だけ（「高橋（徹）」）、試合結果に出身高校 | あり（gameinfo/{年}/…） | 規定到達者＝公式、それ以外＝試合結果を足し上げ（四死球・三振は無いので一球速報で補う） |
| 首都 | tmubl.jp | 規定到達者だけ（stats{年}{haru/aki}.html） | 試合詳細に全員の打数・安打・打点、投手の投球回・自責 | 表はフルネーム、試合詳細は略称＋学年＋高校 | あり（2014年〜） | 東都と同じ |
| 関西学生 | kansaibig6.jp | 規定到達者だけ（OPSなど詳しい） | 試合ごとのPDF | フルネーム＋学年・出身高校 | あり（「過去の成績はこちら」） | 規定到達者＝公式、それ以外＝一球速報 |
| 仙台六大学 | sen6.jp | サイトがGoogleスプレッドシート（Apps Script）から打撃・投手成績を読み込む作り。項目に選手ID・集計時点あり | ― | 氏名＋大学 | 2026年分のみ確認（サイトを今年作り直した様子） | 中身の確認が途中（下記） |
| 北東北 | kitatohoku-u.umineco.jp | **無し**（表彰＝首位打者・最優秀防御率などだけ） | 試合詳細はスコアと投手の投球回だけ | ― | ― | 一球速報 |
| 愛知 | aubl.jp | 公式サイト自体が**一球速報（omyutech）のデータで動いている** | 同左 | ― | 一球速報に2021年度〜 | 一球速報＝公式扱いでよい |
| 関甲新 | **kankoushin.com**（全日本大学野球連盟に載っている kankoushin.jp は売りに出ているドメイン） | 無し | 無し | ― | 無し | 一球速報（首位決定戦・各地区の大会ページあり） |

## わかったこと

- **全選手の公式シーズン成績が取れるのは東京六大学だけ**。他は規定到達者だけか、成績表そのものが無い。
- 規定未満の選手（控え・リリーフ・下級生）が候補には多いので、**規定到達者以外は一球速報で埋める前提**になる。
- 東都・首都は試合ごとの記録が公式にあるが、打数・安打・打点と投手の投球回・自責くらいで、四死球・三振・二塁打などは揃わない。
- 愛知のように連盟が一球速報を公式の速報に使っているところは、一球速報の数字をそのまま公式扱いにできる。関西学生のサイトにも「一球速報」へのリンクがある。
- 名前は姓だけの連盟が多い。出身高校・学年・入学年が付く連盟が多いので、照合は「大学＋姓＋出身高校」で行う。

## 残っている確認

- 仙台六大学：サイトが読み込んでいる Apps Script の公開データを、シーズン指定（2026-autumn など）で読む確認は、自動の安全確認で止められたので未確認。規定到達者だけか全員かも未確認。
- 一球速報のチームの「大会別成績」は JavaScript で読み込まれる。これまでどおり選手ページ（playerTop.action）の大会合計行から取るのが確実（memory: ikkyu-stats-import）。
- 残り18連盟は、選手の多い順に同じ観点で調べる。

## 全国の連盟の公式サイト（全日本大学野球連盟の一覧より）

北海道学生 do6.jp / 札幌学生 satsu6.com / 北東北 kitatohoku-u.umineco.jp / 仙台六 sen6.jp / 南東北 mtu-bbl.jp / 千葉県 cub-channel.net / 関甲新 kankoushin.com（一覧の kankoushin.jp は誤り） / 東京新 new-tokyo-bbl.com / 東京六 big6.gr.jp / 東都 tohto-bbl.com / 首都 tmubl.jp / 神奈川 kubl.jp / 愛知 aubl.jp / 東海地区 tokaibbl.jp / 北陸 hu-bl.com / 関西学生 kansaibig6.jp / 関西六 kan6bb.jp / 阪神 hanshin-bbl.com / 近畿学生 kinkigakusei.org / 京滋 keijidaigaku.com / 広島六 hiroshima-big6.com / 中国地区 cubf5589.com / 四国地区 shikokubaseball.seesaa.net / 九州六 96bbl.com / 福岡六 fukuokabig6league.wixsite.com/my-site-5 / 九州地区 kubu.jp / 南部九州 nkub.jp

## URLの例

- 東京六大学 チーム別全選手：`https://www.big6.gr.jp/system/prog/kojinseiseki_season.php?gs=season&t={H|K|M|R|T|W}&m=pc&k={batting|pitching}&e=league&s={年}{s=春|a=秋}`
- 東京六大学 選手ページ：`kojinseiseki_season_individual.php?gs=season&teamtmp=W&mode=pc&kind=pitching&season=2026a&playerid=AW23KK0`
- 東都 規定到達者：`http://www.tohto-bbl.com/gameinfo/{年}/{1|2|3|4}battrer_{s|a}.html`・`{n}pitcher_{s|a}.html`、試合：`gameinfo/result.php?YEAR=&SEASONID=01|02&LEAGUEID=01..04&GAMEID=`
- 首都 規定到達者：`https://tmubl.jp/stats{年}{haru|aki}.html`、試合詳細は `https://tmubl.jp/game/{年}{春|秋}?ds={年}aki-1` の中に全試合ぶん
- 関西学生：`https://kansaibig6.jp/{年}{spring|autumn}-kozinseiseki/`
