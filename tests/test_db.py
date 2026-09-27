"""DB 초기화: 예전 스키마(문제 카드 기능 이전)의 기존 DB 에 새 컬럼이 자동 추가되는지."""
import sqlite3

from sqlalchemy import inspect

import db


def test_init_db_adds_report_column_to_old_table(tmp_path):
    path = tmp_path / 'old.db'
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255), "
                "password_hash VARCHAR(100), created_at DATETIME)")
    con.execute("CREATE TABLE workout_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, "
                "exercise VARCHAR(50), created_at DATETIME, score INTEGER, summary TEXT, "
                "stats JSON, items JSON)")
    con.execute("INSERT INTO workout_sessions (user_id, exercise, summary, stats, items) "
                "VALUES (1, 'squat', '', '{}', '[]')")
    con.commit()
    con.close()

    engine = db.init_db(f"sqlite:///{path}")
    columns = {c['name'] for c in inspect(engine).get_columns('workout_sessions')}
    assert 'report' in columns
    with db.SessionLocal() as s:  # 기존 행은 그대로, report 는 비어 있음
        assert s.get(db.WorkoutSession, 1).report is None

    db.init_db(f"sqlite:///{path}")  # 두 번 실행해도 오류 없음
