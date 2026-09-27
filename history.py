"""
history.py — 운동 기록 저장·조회 (히스토리 목록 / 상세 / 발전 추이)

로그인한 사용자가 /analyze 를 호출하면 save_session() 으로 기록이 저장되고,
앱은 아래 엔드포인트로 자기 기록만 조회한다.

  GET    /sessions              목록 (최신순, 운동·기간 필터) — 캘린더·기록 목록용
  GET    /sessions/{id}         상세 (당시 분석 응답 그대로, 이미지 포함)
  DELETE /sessions/{id}         삭제
  GET    /progress/{exercise}   발전 추이 (기록별 점수 + 특징별 평균 ratio·지적 비율)
"""

from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

import media
from analyze import REFERENCE
from auth import get_current_user
from db import User, WorkoutSession, as_utc, get_db
from schemas import (FeatureProgress, FeedbackItem, ProgressPoint, ProgressResponse,
                     SessionDetail, SessionSummary)

router = APIRouter(tags=["history"])

# DB 에 저장할 피드백 항목 필드 (이미지는 파일로 따로, 영상 경로·프레임 번호는 버린다)
ITEM_FIELDS = [f for f in FeedbackItem.model_fields if f not in ("ref_image", "user_image")]


# ── 저장 ───────────────────────────────────────────────────────────────────────
def save_session(db, user_id, exercise, summary, items, stats, images):
    """분석 결과를 기록으로 저장하고 id 를 반환한다.

    items  : analyze_for_ui 의 항목 dict 리스트
    images : items 와 같은 순서의 (모범 JPEG, 내 JPEG) 바이트 쌍 (없으면 None)
    """
    session = WorkoutSession(
        user_id=user_id, exercise=exercise, score=stats["score"], summary=summary,
        stats=stats, items=[{k: it.get(k) for k in ITEM_FIELDS} for it in items])
    db.add(session)
    db.flush()  # 이미지 폴더 이름으로 쓸 id 확보
    try:
        for it, (ref_jpeg, user_jpeg) in zip(items, images):
            media.save_image(session.id, f"{it['key']}_ref", ref_jpeg)
            media.save_image(session.id, f"{it['key']}_user", user_jpeg)
        db.commit()
    except Exception:
        db.rollback()
        media.delete_session_media(session.id)
        raise
    return session.id


# ── 헬퍼 ───────────────────────────────────────────────────────────────────────
def _to_utc(dt):
    """쿼리 파라미터 시각을 UTC 로 (시간대 없으면 UTC 로 간주)."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _top_faults(stats, n=2):
    counts = Counter(m["name"] for r in stats["reps"] for m in r["metrics"] if m["fault"])
    return [name for name, _ in counts.most_common(n)]


def _get_own_session(db, user, session_id):
    s = db.get(WorkoutSession, session_id)
    if s is None or s.user_id != user.id:  # 남의 기록도 '없음'으로 응답 (존재 여부 노출 방지)
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    return s


# ── 엔드포인트 ─────────────────────────────────────────────────────────────────
@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(exercise: str | None = None,
                  since: datetime | None = Query(None, description="이 시각 이후 (ISO 8601)"),
                  until: datetime | None = Query(None, description="이 시각 이전 (ISO 8601)"),
                  limit: int = Query(50, ge=1, le=200),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(WorkoutSession).where(WorkoutSession.user_id == user.id)
    if exercise:
        q = q.where(WorkoutSession.exercise == exercise)
    if since:
        q = q.where(WorkoutSession.created_at >= _to_utc(since))
    if until:
        q = q.where(WorkoutSession.created_at < _to_utc(until))
    q = q.order_by(WorkoutSession.created_at.desc(), WorkoutSession.id.desc()).limit(limit)
    return [
        SessionSummary(id=s.id, exercise=s.exercise, created_at=as_utc(s.created_at),
                       score=s.score, rep_count=s.stats["rep_count"],
                       top_faults=_top_faults(s.stats))
        for s in db.scalars(q)
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: int,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _get_own_session(db, user, session_id)
    items = [
        FeedbackItem(**it,
                     ref_image=media.load_image_uri(s.id, f"{it['key']}_ref"),
                     user_image=media.load_image_uri(s.id, f"{it['key']}_user"))
        for it in s.items
    ]
    return SessionDetail(session_id=s.id, created_at=as_utc(s.created_at), exercise=s.exercise,
                         summary=s.summary, items=items, stats=s.stats)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _get_own_session(db, user, session_id)
    db.delete(s)
    db.commit()
    media.delete_session_media(session_id)


@router.get("/progress/{exercise}", response_model=ProgressResponse)
def progress(exercise: str, limit: int = Query(100, ge=1, le=500),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """운동별 발전 추이. 최근 limit 건을 오래된 순으로 돌려준다.

    특징별 avg_ratio(회차 평균 '허용오차 대비 벗어난 정도')가 내려가면 좋아지고 있는 것.
    """
    if exercise not in REFERENCE:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 운동입니다: {exercise}")
    q = (select(WorkoutSession)
         .where(WorkoutSession.user_id == user.id, WorkoutSession.exercise == exercise)
         .order_by(WorkoutSession.created_at.desc(), WorkoutSession.id.desc()).limit(limit))
    points = []
    for s in reversed(list(db.scalars(q))):
        # (view, feature) 별로 회차 값을 모은다 (런지처럼 같은 특징 이름이 두 뷰에 있을 수 있음)
        by_feat = {}
        for r in s.stats["reps"]:
            for m in r["metrics"]:
                by_feat.setdefault((r["view"], m["feature"]), []).append(m)
        features = [
            FeatureProgress(view=view, feature=feat, name=ms[0]["name"],
                            avg_ratio=round(sum(m["ratio"] for m in ms) / len(ms), 2),
                            fault_rate=round(sum(m["fault"] for m in ms) / len(ms), 2))
            for (view, feat), ms in by_feat.items()
        ]
        points.append(ProgressPoint(session_id=s.id, created_at=as_utc(s.created_at),
                                    score=s.score, features=features))
    return ProgressResponse(exercise=exercise, points=points)
