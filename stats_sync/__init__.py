"""連盟公式サイトから大学リーグ戦の成績を取り込む（main_stats.py から使う）。

方針（2026-11-27 決定）:
- 成績は各連盟の公式サイトの数字を正とする。一球速報は規約でスクレイピングが禁止されているので使わない。
- 取り込んだ行には stats.source / source_url / fetched_at を入れる。locked=true の行は触らない。
- 選手と連盟サイトの選手の対応は player_stat_links に保存し、次回からは名前照合をしない。
調査メモ: docs/stats_sources_survey.md
"""
