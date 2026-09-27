# PoseFeedback (iOS 앱)

운동 자세 피드백 백엔드(`/analyze`)를 호출하는 SwiftUI iPhone 앱.

## 사전 준비
- **Xcode 정식판** 설치 (App Store, 7GB+). 현재 맥엔 Command Line Tools 만 있어 앱 빌드 불가.
- 백엔드 컨테이너 실행 중이어야 함: `docker run -p 8000:8080 pose-api`
  (시뮬레이터는 맥의 `localhost:8000` 에 바로 접속됨 — 회사/학교 네트워크 무관)

## 프로젝트 열기
프로젝트는 `xcodegen` 으로 이미 생성돼 있다 (`project.yml` 기반).
```bash
open ios/PoseFeedback.xcodeproj
```
`project.yml` 을 고쳤거나 소스를 추가하면 재생성:
```bash
cd ios && xcodegen generate
```

로컬 http 접속 허용(`NSAllowsLocalNetworking`)은 `project.yml` 에 이미 들어가 있어
별도 Info 설정이 필요 없다.

## 실행
- 상단에서 시뮬레이터(예: iPhone 15) 선택 → **Run (⌘R)**
- 첫 화면에서 **회원가입/로그인** (서버 주소는 로그인 화면 하단 또는 설정 탭에서 변경)
- **분석** 탭: 운동 선택 → 측면/정면 영상 선택(시뮬레이터 사진앱에 영상이 있어야 함) → **분석하기**
  - 고른 영상은 업로드 전에 540p 로 압축된다(60초 초과 영상은 거부)
  - 결과 화면에서 항목을 탭하면 모범 vs 내 자세 비교가 나온다. 결과는 자동으로 기록에 저장된다.
- **기록** 탭: 운동 캘린더(연속 운동일·이번 주), 기록 목록(탭하면 당시 결과), 운동별 발전 추이 그래프
- **설정** 탭: 로그아웃, 서버 주소, 회원 탈퇴

### 시뮬레이터에 테스트 영상 넣기
시뮬레이터 사진 보관함이 비어 있으면, 맥의 영상 파일(예: `data/raw/user_squat_side_raw.mp4`)을
**시뮬레이터 창으로 드래그&드롭** 하면 사진앱에 추가된다.

## 실기기 / 외부 테스트
서버 주소는 코드가 아니라 앱의 **설정 탭(또는 로그인 화면 하단)** 에서 바꾼다.
- 같은 WiFi 실기기: 맥 LAN IP (`http://192.168.x.x:8000`)
- 배포 서버: `https://도메인`

## 구성
```
PoseFeedbackApp.swift   앱 진입점 + 로그인 여부에 따른 화면 전환(탭)
AppState.swift          로그인 토큰·서버 주소 등 전역 상태 (토큰 만료 시 자동 로그아웃)
AuthView.swift          로그인/회원가입 + 서버 주소 시트
ContentView.swift       분석 탭: 운동·영상 선택 + 분석 요청
ResultsView.swift       결과 요약(점수) + 항목 목록 + 모범/내 자세 비교
HistoryView.swift       기록 탭: 캘린더·연속 기록·기록 목록·상세
ProgressChartView.swift 운동별 발전 추이 그래프 (Swift Charts)
SettingsView.swift      설정 탭: 계정·서버·회원 탈퇴
VideoCompressor.swift   업로드 전 540p 압축 + 길이 제한
Keychain.swift          로그인 토큰 보관
APIClient.swift         백엔드 호출 (인증·분석·기록)
Models.swift            API 응답 모델
```
