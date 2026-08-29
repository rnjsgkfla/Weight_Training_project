"""
api.py — FastAPI 백엔드: 영상 업로드 → 자세 피드백 JSON

기존 분석 파이프라인(analyze.py)을 그대로 감싼다. 프론트(앱/웹)가 운동 종류와
측면·정면 영상을 올리면, 반복별 피드백 항목과 '모범 vs 내 자세' 비교 이미지를
JSON 으로 돌려준다.

동시 사용자 대응:
  요청마다 tempfile.mkdtemp() 로 임시 작업폴더를 격리하고, 처리 후 삭제한다
  (기존 고정 경로 data/processed/_user 를 쓰지 않는다).

실행:  ./venv/bin/uvicorn api:app --reload   → http://127.0.0.1:8000/docs 에서 테스트
"""

import os
import base64
import tempfile
import shutil

import cv2
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from analyze import analyze_for_ui, frame_at, REFERENCE, EXERCISE_KR

app = FastAPI(title="운동 자세 피드백 API", version="0.1.0")


# ── 응답 스키마 ────────────────────────────────────────────────────────────────
class FeedbackItem(BaseModel):
    key: str            # 항목 식별자 (프론트에서 선택용, 항상 고유)
    label: str          # 목록에 표시할 이름
    detail: str         # 상세 설명 (markdown)
    ok: bool            # 결함 없이 양호한 항목이면 True
    ref_image: str | None   # 모범 자세 프레임 (data:image/png;base64,...)
    user_image: str | None  # 내 자세 프레임 (data:image/png;base64,...)


class AnalyzeResponse(BaseModel):
    exercise: str
    summary: str
    items: list[FeedbackItem]


# ── 헬퍼 ───────────────────────────────────────────────────────────────────────
def _img_data_uri(video_path, frame_number):
    """영상의 특정 프레임을 JPEG data URI 문자열로 인코딩한다(없으면 None).

    비교용 사진이라 JPEG(품질 80)로 인코딩해 응답 크기를 줄인다(PNG 대비 5~8배 작음).
    """
    img = frame_at(video_path, frame_number)  # RGB
    if img is None:
        return None
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)  # imencode 는 BGR 기준
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


async def _save_upload(upload, workdir, view):
    """업로드 파일을 작업폴더에 저장하고 경로를 반환한다."""
    ext = os.path.splitext(upload.filename or "")[1] or ".mp4"
    path = os.path.join(workdir, f"user_{view}{ext}")
    with open(path, "wb") as f:
        f.write(await upload.read())
    return path


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
):
    """운동 종류와 측면·정면 영상을 받아 반복별 자세 피드백을 반환한다.

    - exercise 가 지원하지 않는 뷰의 영상은 무시된다(예: 사이드레터럴레이즈의 측면).
    - 둘 중 하나만 올려도 된다.
    """
    if exercise not in REFERENCE:
        raise HTTPException(status_code=400,
                            detail=f"지원하지 않는 운동입니다: {exercise} (가능: {list(REFERENCE)})")
    if side_video is None and front_video is None:
        raise HTTPException(status_code=400, detail="측면 또는 정면 영상을 하나 이상 올려주세요.")

    workdir = tempfile.mkdtemp(prefix="pose_")
    try:
        side_path = await _save_upload(side_video, workdir, "side") if side_video else None
        front_path = await _save_upload(front_video, workdir, "front") if front_video else None

        try:
            items, summary = analyze_for_ui(exercise, side_path, front_path, workdir=workdir)
        except FileNotFoundError:
            # 기준(모범) 데이터가 아직 준비 안 된 운동 (예: 사이드레터럴레이즈 원본 미포함)
            raise HTTPException(
                status_code=503,
                detail=f"'{EXERCISE_KR.get(exercise, exercise)}' 기준 데이터가 아직 준비되지 않았습니다.")

        out_items = [
            FeedbackItem(
                key=it["key"], label=it["label"], detail=it["detail"], ok=it["ok"],
                ref_image=_img_data_uri(it["ref_video"], it["ref_frame"]),
                user_image=_img_data_uri(it["user_video"], it["user_frame"]),
            )
            for it in items
        ]
        return AnalyzeResponse(exercise=exercise, summary=summary, items=out_items)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
