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

`scoring.py` — 화면의 판정(양호 / 고칠 점)과 **같은 결과**로 점수를 계산한다. 그래서 점수와 판정이 어긋나지 않는다.

| 점수 | 의미 |
|---|---|
| 80~100 | 모든 회차에서 지적 없음. 허용오차에서 멀수록(모범에 가까울수록) 100 에 가깝다 |
| 0~79 | 지적된 항목이 있음. 자주·크게 벗어날수록 낮다 |

항목(뷰·특징 = 문제 카드 하나)별 점수 S를 구해 가중합한다.
- 지적 없음: `S = 100 − 20 × m` (m = 전 구간 평균 `min(나쁜 방향 편차 / 허용오차, 1)`, 좋은 방향 편차는 0)
- 지적 있음: `S = 79 × (1 − p)`, `p = ½ × 지적 회차 비율 + ½ × min((심각도 − 1) / 2, 1)`
- 총점 = `Σ 가중치 × S` (올린 영상 방향의 항목만, 가중치 재정규화). 지적이 하나라도 있으면 79 이하.
- 런지는 핵심 실수가 측면에서 보여 측면 80% / 정면 20%로 두고, 지적된 항목의 가중치를
  `× (1 + 2p)` 로 키운다 (`FAULT_EMPHASIS`). 지적 없는 항목이 심한 문제의 감점을 메우지 못하게 한다.

나쁜 방향·허용오차는 `judge.py` 판정 규칙을 그대로 쓰고, 항목 가중치는 `scoring.py` 의 `SCORE_WEIGHTS` 에서 바꾼다.

## 테스트
```bash
./venv/bin/pip install -r requirements-dev.txt
python build_references.py            # 기준 데이터가 없으면 먼저 생성 (없으면 관련 테스트는 skip)
./venv/bin/python -m pytest tests
```
`test_analyze_regression.py` 는 샘플 영상(`data/raw/user_squat_*`)의 반복 수·점수·지적 항목을
고정해 둔 회귀 테스트다. 판정 규칙을 의도적으로 바꿨다면 기대값을 함께 갱신한다.

## Lightsail HTTPS 배포

현재 공개 API 주소는 `https://posefeedback.duckdns.org`입니다.
DuckDNS의 A 레코드는 Lightsail 고정 IP를 가리켜야 하며, Lightsail 방화벽에서
TCP 80·443을 허용해야 합니다. `.env`에 `PUBLIC_DOMAIN=posefeedback.duckdns.org`를 설정합니다.

```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
curl --fail https://posefeedback.duckdns.org/health
```

HTTPS 배포 후 업데이트에도 위 두 Compose 파일을 함께 지정합니다.
Caddy가 인증서를 자동 발급·갱신하고 인증서는 `caddy_data` 볼륨에 보관합니다.
API의 8000 포트는 서버 내부에만 바인딩되며 DB와 기존 기록 볼륨은 유지됩니다.
iOS 앱의 로그인 화면 또는 설정에서 서버 주소를 위 HTTPS 주소로 변경하면
맥의 SSH 터널 없이 AWS에 직접 접속합니다.

## 촬영 가이드 영상 배포
촬영 가이드 영상은 분석용 원본과 별도로 생성합니다. Ubuntu 서버에 `ffmpeg`를 설치한 뒤:

```bash
sudo apt-get install -y ffmpeg
python3 build_guides.py
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --no-deps caddy
```

`data/guides/`의 다섯 기준 영상만 Caddy의 `/guides/` 경로로 제공합니다.
예: `https://posefeedback.duckdns.org/guides/squat-side.mp4`.
원본을 교체하면 생성 스크립트를 다시 실행합니다. 기존 원본과 분석 기준 데이터는 변경하지 않습니다.
영상은 H.264 MP4(최대 720px, 무음)이며 구간 다운로드를 지원합니다. 로컬 API만 실행하는 환경에서는 이 정적 경로도 별도로 제공해야 합니다.

## 웹 데모 실행 (Gradio)
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
scoring.py             자세 점수 (판정 결과 → 항목별 점수 → 가중합)
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
