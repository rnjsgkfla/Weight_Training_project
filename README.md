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
| POST | `/analyze` | multipart: `exercise`, `side_video`, `front_video` → 반복별 피드백 + 비교 이미지 + 통계(`stats`: 점수·반복 수·회차별 측정값) JSON. 로그인 토큰을 보내면 기록으로 저장하고 `session_id` 반환. 사람이 없거나 전신이 안 보이는 영상은 분석하지 않고 `stats.warnings` 로 이유를 알려준다. `issues` = 문제별 카드(같은 문제를 회차와 무관하게 묶어 심각한 순, 상위 3개는 DTW 로 맞춘 모범/내 자세 비교 프레임 포함), `good_points` = 잘한 항목 |
| POST | `/auth/signup` | JSON `{email, password(8자 이상)}` → `{access_token}` (가입 후 바로 로그인) |
| POST | `/auth/login` | JSON `{email, password}` → `{access_token}` (유효기간 30일) |
| GET / DELETE | `/me` 🔒 | 내 계정 조회 / 회원 탈퇴 (기록·이미지 모두 삭제) |
| GET | `/sessions` 🔒 | 내 운동 기록 목록 (최신순). 쿼리: `exercise`, `since`, `until`(ISO 8601), `limit` |
| GET / DELETE | `/sessions/{id}` 🔒 | 기록 상세(당시 분석 응답 그대로, 이미지 포함) / 삭제 |
| GET | `/progress/{exercise}` 🔒 | 발전 추이: 기록별 점수 + 특징별 평균 ratio·지적 비율 (오래된 순) |
| GET | `/docs` | 자동 생성 API 문서(Swagger) |

🔒 = `Authorization: Bearer <access_token>` 헤더 필요.

예시:
```bash
curl -F exercise=squat -F side_video=@data/raw/user_squat_side_raw.mp4 http://localhost:8000/analyze
```

## 다른 컴퓨터에서 처음부터 실행 (백엔드 → iOS 앱)

GitHub 에서 받은 뒤 백엔드부터 앱까지 실행하는 전체 순서.

### 사전 준비
- Git, Docker Desktop
- (iOS 앱까지 실행할 경우) macOS + **Xcode 정식판** + iOS 시뮬레이터 런타임, `brew install xcodegen`

### 1) 코드 받기
```bash
git clone https://github.com/rnjsgkfla/Weight_Training_project.git
cd Weight_Training_project
# 이미 클론했다면:  git pull origin main
```

### 2) 백엔드 실행 (Docker Compose · 권장)
API 와 Postgres(운동 기록 DB)를 함께 띄운다. 서버 배포도 같은 방식이다.
```bash
cp .env.example .env                # POSTGRES_PASSWORD, JWT_SECRET 값을 바꾼다
docker compose up -d --build        # 기준 데이터까지 이미지에 생성 (~2~3분)
                                    # http://localhost:8000/docs 로 확인
```
> `data/processed`(기준 데이터)는 커밋되지 않지만, 빌드 시 `build_references.py` 가 원본 영상
> (`data/raw`)에서 재생성해 이미지에 굽는다. 포트는 `호스트:컨테이너` = `8000:8080`.
> DB 와 기록 이미지는 Docker 볼륨(`pgdata`, `media`)에 남아서 컨테이너를 다시 만들어도 유지된다
> (`docker compose down -v` 는 볼륨까지 지우므로 주의).

백엔드만 Python 으로 직접 띄우려면:
```bash
python3.11 -m venv venv
./venv/bin/pip install -r requirements-api.txt
python build_references.py            # 원본 영상 → 기준 데이터 생성
./venv/bin/uvicorn api:app --reload   # http://127.0.0.1:8000/docs
```
> 이 경우 DB 는 `data/app.db`(SQLite), 기록 이미지는 `data/media/` 에 저장된다.
> `JWT_SECRET` 을 설정하지 않으면 재시작할 때마다 로그인 토큰이 무효가 된다.

### 3) iOS 앱 실행 (macOS + Xcode)
백엔드가 **먼저 켜져 있어야** 한다(시뮬레이터는 맥의 `localhost:8000` 에 바로 접속 — 네트워크 무관).
```bash
cd ios
xcodegen generate                   # .xcodeproj 생성 (gitignore 대상이라 pull 후 매번 실행)
open PoseFeedback.xcodeproj          # Xcode 로 열기
```
Xcode 상단에서 시뮬레이터(예: iPhone 17) 선택 → **Run (⌘R)**.

CLI 로 빌드·실행하려면(Xcode 없이):
```bash
xcodebuild -project PoseFeedback.xcodeproj -scheme PoseFeedback -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 17' -derivedDataPath /tmp/PoseFeedbackBuild build
xcrun simctl boot "iPhone 17"; open -a Simulator
xcrun simctl install "iPhone 17" /tmp/PoseFeedbackBuild/Build/Products/Debug-iphonesimulator/PoseFeedback.app
xcrun simctl launch "iPhone 17" com.posefeedback.app
```
> iCloud 동기화 폴더(예: `~/Documents`)에서 빌드하면 codesign "detritus" 오류가 날 수 있어
> `-derivedDataPath /tmp/...` 로 iCloud 밖에서 빌드한다. Xcode GUI Run 은 기본 DerivedData
> (iCloud 밖)를 써서 문제없다.

### 끄기 / 다시 켜기
```bash
docker compose stop     # 중지 (데이터 유지)
docker compose start    # 다시 실행 (재빌드 불필요)
docker compose logs -f api   # 서버 로그 보기
```

## 자세 점수

`scoring.py` — 모범 반복과 DTW 로 맞춘 대응쌍에서 특징별 평균 절대 오차 D 를 구하고,
허용 오차 T 로 정규화(e = min(D/T, 1))한 뒤 가중합 E 로 `점수 = 100 × (1 − E)` (0~100).

| 운동 | 계산 영상 | 항목 (가중치) |
|---|---|---|
| 스쿼트 | 측면 | 무릎 각도 0.40 · 골반 높이 0.35 · 상체 기울기 0.25 |
| 런지 | 측면 | 앞무릎 0.35 · 뒷무릎 0.20 · 골반 높이 0.25 · 상체 기울기 0.20 |
| 사이드 레터럴 레이즈 | 정면 | 어깨 각도(골반–어깨–팔꿈치) 0.35 · 팔꿈치 0.20 · 손목 높이 0.30 · 상체 기울기 0.15 (좌우는 평균 오차 후 정규화) |

가중치·허용 오차는 `scoring.py` 상단 상수에서 바꾼다.

## 테스트
```bash
./venv/bin/pip install -r requirements-dev.txt
python build_references.py            # 기준 데이터가 없으면 먼저 생성 (없으면 관련 테스트는 skip)
./venv/bin/python -m pytest tests
```
`test_analyze_regression.py` 는 샘플 영상(`data/raw/user_squat_*`)의 반복 수·점수·지적 항목을
고정해 둔 회귀 테스트다. 판정 규칙을 의도적으로 바꿨다면 기대값을 함께 갱신한다.

## 웹 데모 (Gradio)
```bash
./venv/bin/pip install -r requirements.txt   # gradio 포함
./venv/bin/python app.py                      # http://127.0.0.1:7860
```

## 구조

```
api.py                 FastAPI 앱 + /analyze (분석 파이프라인 래퍼, 로그인 시 기록 저장)
auth.py                회원가입·로그인 (bcrypt + JWT)
history.py             운동 기록 목록·상세·삭제·발전 추이
db.py                  DB 연결·테이블 (SQLAlchemy, SQLite/Postgres)
media.py               기록 비교 이미지 파일 저장
schemas.py             API 요청/응답 스키마
issues.py              문제별 카드 묶기·정렬 + 비교 프레임(문제 관절 표시) 생성
scoring.py             자세 점수 (DTW 평균 오차 → 정규화 → 가중합)
docker-compose.yml     API + Postgres
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
ios/                   iOS 앱 (SwiftUI) — project.yml 로 xcodegen 생성
tests/                 pytest (판정 수치 단위 테스트 · 샘플 영상 회귀 · API 스키마)
```
