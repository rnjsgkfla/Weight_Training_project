# 운동 자세 피드백 API

사용자의 운동 영상을 기준(모범) 영상과 비교해 반복별 자세 피드백을 주는 FastAPI 백엔드.
MediaPipe 로 관절을 뽑아 정규화·DTW 정렬 후 규칙 기반으로 결함을 판정한다.

- 지원 운동: 스쿼트(측면·정면), 런지(측면·정면), 사이드 레터럴 레이즈(정면, 원본 준비 시)
- 파이프라인: `keypoint_extractor → smooth → normalize → features → rep 분할 → DTW → judge`

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 헬스 체크 |
| GET | `/exercises` | 지원 운동과 필요한 뷰 목록 |
| POST | `/analyze` | multipart: `exercise`, `side_video`, `front_video` → 반복별 피드백 + 비교 이미지 JSON |
| GET | `/docs` | 자동 생성 API 문서(Swagger) |

예시:
```bash
curl -F exercise=squat -F side_video=@data/raw/user_squat_side_raw.mp4 http://localhost:8000/analyze
```

## 실행

### Docker (권장 — 어느 컴퓨터든 동일)
```bash
docker build -t pose-api .
docker run -p 8000:8080 pose-api   # http://localhost:8000/docs
```
빌드 시 `build_references.py` 가 원본 영상(`data/raw`)에서 기준 데이터를 생성해 이미지에 굽는다.

### Python 직접
```bash
python3.11 -m venv venv
./venv/bin/pip install -r requirements-api.txt
python build_references.py            # 원본 영상 → 기준 데이터 생성
./venv/bin/uvicorn api:app --reload    # http://127.0.0.1:8000/docs
```

## 웹 데모 (Gradio)
```bash
./venv/bin/pip install -r requirements.txt   # gradio 포함
./venv/bin/python app.py                      # http://127.0.0.1:7860
```

## 구조

```
api.py                 FastAPI 엔드포인트 (얇은 래퍼)
analyze.py             파이프라인 오케스트레이션 + UI용 구조화
build_references.py    원본 영상 → 운동별 기준 데이터 일괄 생성
keypoint_extractor.py  MediaPipe 관절 추출
smooth_landmarks.py    Savitzky-Golay 스무딩
normalize_landmarks.py 골반중심·상체길이 정규화 + 종횡비 보정
features.py            운동·뷰별 특징(각도/비율) 추출
angles.py              각도 계산 엔진 + 운동별 각도 정의
rep_segmentation.py    반복 분할 (히스테리시스)
rep_features.py        반복별 특징 슬라이싱
dtw.py                 DTW 위상 정렬
judge.py               운동별 규칙 판정 + 피드백 생성
app.py                 Gradio 웹 UI
```
