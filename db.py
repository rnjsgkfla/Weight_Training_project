"""
db.py — DB 연결과 테이블 정의 (SQLAlchemy 2.x)

로컬 기본값은 SQLite 파일(data/app.db), Docker Compose·배포는 DATABASE_URL 로 Postgres 를 쓴다.
스키마는 앱 시작 시 create_all 로 만든다 (스키마가 안정되면 Alembic 마이그레이션 도입).

테이블은 두 개뿐이다:
  users            : 계정
  workout_sessions : 분석 1회 = 기록 1건. 통계(stats)와 피드백 항목(items)은 기록 단위로만
                     읽으므로 JSON 컬럼에 통째로 둔다. 비교 이미지는 파일로 따로 저장(history.py).
"""

import os
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./data/app.db"

SessionLocal = sessionmaker()


def _now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    sessions: Mapped[list["WorkoutSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exercise: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    score: Mapped[int | None]
    summary: Mapped[str] = mapped_column(Text)
    stats: Mapped[dict] = mapped_column(JSON)   # analyze_for_ui 의 stats 그대로
    items: Mapped[list] = mapped_column(JSON)   # 피드백 항목 (이미지·영상 경로 제외)

    user: Mapped[User] = relationship(back_populates="sessions")


def init_db(url=None):
    """엔진을 만들고 테이블을 생성한다. 앱 시작 시(또는 테스트에서) 한 번 호출."""
    url = url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    kwargs = {}
    if url.startswith("sqlite"):
        # FastAPI 는 요청을 스레드풀에서 처리하므로 SQLite 의 같은-스레드 제한을 푼다
        kwargs["connect_args"] = {"check_same_thread": False}
        path = url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    Base.metadata.create_all(engine)
    SessionLocal.configure(bind=engine)
    return engine


def get_db():
    """요청마다 DB 세션을 열고 끝나면 닫는 FastAPI 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def as_utc(dt):
    """SQLite 는 시간대를 버리고 돌려주므로(UTC 로 저장됨) UTC 를 다시 붙인다."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
