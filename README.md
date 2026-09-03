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

### 2) 백엔드 실행 (Docker · 권장)
```bash
docker build -t pose-api .          # 기준 데이터까지 이미지에 생성 (~2~3분)
docker run -p 8000:8080 pose-api    # http://localhost:8000/docs 로 확인
```
> `data/processed`(기준 데이터)는 커밋되지 않지만, 빌드 시 `build_references.py` 가 원본 영상
> (`data/raw`)에서 재생성해 이미지에 굽는다. 포트는 `호스트:컨테이너` = `8000:8080`.

백엔드만 Python 으로 직접 띄우려면:
```bash
python3.11 -m venv venv
./venv/bin/pip install -r requirements-api.txt
python build_references.py            # 원본 영상 → 기준 데이터 생성
./venv/bin/uvicorn api:app --reload   # http://127.0.0.1:8000/docs
```

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
docker ps               # 실행 중 컨테이너 확인
docker stop <ID>        # 백엔드 중지
docker run -p 8000:8080 pose-api   # 다시 실행 (이미지 남아있어 재빌드 불필요)
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
ios/                   iOS 앱 (SwiftUI) — project.yml 로 xcodegen 생성
```
