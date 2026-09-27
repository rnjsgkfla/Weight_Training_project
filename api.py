"""
api.py — FastAPI 백엔드: 영상 업로드 → 자세 피드백 JSON

기존 분석 파이프라인(analyze.py)을 그대로 감싼다. 프론트(앱/웹)가 운동 종류와
측면·정면 영상을 올리면, 반복별 피드백 항목과 '모범 vs 내 자세' 비교 이미지를
JSON 으로 돌려준다. 로그인 토큰과 함께 호출하면 결과를 운동 기록으로 저장한다
(회원가입·로그인은 auth.py, 기록 조회는 history.py).

동시 사용자 대응:
  요청마다 tempfile.mkdtemp() 로 임시 작업폴더를 격리하고, 처리 후 삭제한다
  (기존 고정 경로 data/processed/_user 를 쓰지 않는다).

실행:  ./venv/bin/uvicorn api:app --reload   → http://127.0.0.1:8000/docs 에서 테스트
"""

import os
import tempfile
import shutil
from contextlib import asynccontextmanager

import cv2
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

import auth
import history
from analyze import analyze_for_ui, frame_at, REFERENCE, EXERCISE_KR
from db import init_db, get_db
import issues as issue_cards
from media import jpeg_data_uri
from schemas import AnalyzeResponse, FeedbackItem


@asynccontextmanager
async def lifespan(_app):
    init_db()  # DATABASE_URL (기본: data/app.db SQLite)
    yield


app = FastAPI(title="운동 자세 피드백 API", version="0.2.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(history.router)

# 업로드 최대 크기 (스쿼트 몇 회 영상이면 보통 수십 MB 이내). 초과 시 413 으로 거부해
# 거대 파일이 디스크를 채우는 것을 막는다.
MAX_UPLOAD_MB = 100
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


# ── 헬퍼 ───────────────────────────────────────────────────────────────────────
def _jpeg(video_path, frame_number):
    """영상의 특정 프레임을 JPEG 바이트로 인코딩한다(없으면 None).

    비교용 사진이라 JPEG(품질 80)로 인코딩해 응답 크기를 줄인다(PNG 대비 5~8배 작음).
    """
    img = frame_at(video_path, frame_number)  # RGB
    if img is None:
        return None
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)  # imencode 는 BGR 기준
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return None
    return buf.tobytes()


async def _save_upload(upload, workdir, view):
    """업로드 파일을 작업폴더에 저장하고 경로를 반환한다.

    큰 영상도 메모리에 통째로 올리지 않도록 1MB 청크로 스트리밍 저장하고,
    누적 크기가 MAX_UPLOAD_BYTES 를 넘으면 413 으로 거부한다(디스크 고갈 방지).
    """
    ext = os.path.splitext(upload.filename or "")[1] or ".mp4"
    path = os.path.join(workdir, f"user_{view}{ext}")
    written = 0
    with open(path, "wb") as f:
        while chunk := await upload.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"영상이 너무 큽니다. {MAX_UPLOAD_MB}MB 이하로 올려주세요.")
            f.write(chunk)
    return path


def _analyze_and_encode(exercise, side_path, front_path, workdir):
    """무거운 동기 작업(분석 파이프라인 + 프레임 인코딩)을 한 함수로 묶는다.

    OpenCV/MediaPipe 는 CPU·IO 를 오래 잡는 동기 코드라, 엔드포인트에서 이 함수를
    스레드풀로 오프로드해 이벤트 루프가 막히지 않게 한다.
    """
    items, summary, stats, report = analyze_for_ui(exercise, side_path, front_path, workdir=workdir)
    # (모범, 내 자세) JPEG — 응답에 data URI 로 넣고, 로그인 상태면 기록 이미지로도 저장한다
    images = [(_jpeg(it["ref_video"], it["ref_frame"]), _jpeg(it["user_video"], it["user_frame"]))
              for it in items]
    # 문제 카드 썸네일·비교 프레임 {이미지 이름: JPEG} (작업 폴더가 지워지기 전에 그린다)
    frames, names = issue_cards.collect_frames(report["issues"])
    report_images = dict(zip(names, issue_cards.render_frames(frames)))
    report = {"issues": issue_cards.issue_meta(report["issues"]), "good_points": report["good_points"]}
    return items, summary, stats, images, report, report_images


# ── 엔드포인트 ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/exercises")
def exercises():
    """지원 운동과 필요한 뷰 목록. 프론트가 업로드 UI 를 구성할 때 사용."""
    return {ex: {"name": EXERCISE_KR.get(ex, ex), "views": list(views)}
            for ex, views in REFERENCE.items()}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    exercise: str = Form("squat"),
    side_video: UploadFile | None = File(None),
    front_video: UploadFile | None = File(None),
    user=Depends(auth.get_optional_user),
    db: Session = Depends(get_db),
):
    """운동 종류와 측면·정면 영상을 받아 반복별 자세 피드백을 반환한다.

    - exercise 가 지원하지 않는 뷰의 영상은 무시된다(예: 사이드레터럴레이즈의 측면).
    - 둘 중 하나만 올려도 된다.
    - 로그인 토큰(Authorization: Bearer)과 함께 호출하면 결과를 기록으로 저장하고
      session_id 를 돌려준다. 반복을 하나도 인식하지 못한 결과는 저장하지 않는다.
      (점수용 방향 영상이 없어 점수가 null 이어도 피드백은 저장한다)
    """
    if exercise not in REFERENCE:
        raise HTTPException(status_code=400,
                            detail=f"지원하지 않는 운동입니다: {exercise} (가능: {list(REFERENCE)})")

    workdir = tempfile.mkdtemp(prefix="pose_")
    try:
        # 이 운동이 실제로 쓰는 뷰의 영상만 저장한다 (예: 사이드레터럴레이즈는 정면만).
        supported = REFERENCE[exercise]
        paths = {}
        for view, upload in (("side", side_video), ("front", front_video)):
            if upload is not None and view in supported:
                paths[view] = await _save_upload(upload, workdir, view)
        if not paths:
            raise HTTPException(status_code=400,
                                detail=f"'{EXERCISE_KR.get(exercise, exercise)}'에 필요한 뷰"
                                       f"({', '.join(supported)}) 영상을 하나 이상 올려주세요.")

        try:
            # 무거운 동기 작업은 스레드풀로 오프로드 (이벤트 루프 블로킹 방지)
            items, summary, stats, images, report, report_images = await run_in_threadpool(
                _analyze_and_encode, exercise, paths.get("side"), paths.get("front"), workdir)
        except ValueError as e:
            # 읽을 수 없는/빈 영상 등 잘못된 입력 → 사용자 잘못이므로 400
            raise HTTPException(status_code=400, detail=str(e))
        except FileNotFoundError:
            # 기준(모범) 데이터가 아직 준비 안 된 운동 (예: 사이드레터럴레이즈 원본 미포함)
            raise HTTPException(
                status_code=503,
                detail=f"'{EXERCISE_KR.get(exercise, exercise)}' 기준 데이터가 아직 준비되지 않았습니다.")

        session_id = None
        if user is not None and stats["reps"]:  # 반복을 하나라도 분석했으면 저장 (점수가 없어도)
            session_id = await run_in_threadpool(
                history.save_session, db, user.id, exercise, summary, items, stats, images,
                report, report_images)

        out_items = [
            FeedbackItem(**{k: it.get(k) for k in history.ITEM_FIELDS},
                         ref_image=jpeg_data_uri(ref), user_image=jpeg_data_uri(usr))
            for it, (ref, usr) in zip(items, images)
        ]
        out_issues = issue_cards.with_images(
            report["issues"], lambda name: jpeg_data_uri(report_images.get(name)))
        return AnalyzeResponse(exercise=exercise, summary=summary, items=out_items,
                               issues=out_issues, good_points=report["good_points"],
                               stats=stats, session_id=session_id)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
