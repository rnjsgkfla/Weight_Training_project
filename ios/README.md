# PoseFeedback iOS 앱

운동 촬영·분석, 자세 비교, 기록 확인을 제공하는 SwiftUI iPhone 앱입니다. 백엔드 실행과 API 설명은 [프로젝트 README](../README.md)를 참고합니다.

## 개발 환경

- macOS와 Xcode 정식판
- 설치된 iOS 시뮬레이터 런타임 또는 iOS 17.0 이상 iPhone
- XcodeGen
- 접근 가능한 PoseFeedback 백엔드

## 프로젝트 생성과 실행

저장소 루트에서 실행합니다.

```bash
brew install xcodegen
cd ios
xcodegen generate
open PoseFeedback.xcodeproj
```

`.xcodeproj`는 Git에서 제외되는 생성 파일입니다. 최초 클론 후, `project.yml` 수정 후, 소스 파일 추가·삭제 후에는 다시 생성합니다.

Xcode에서 `PoseFeedback` 스킴과 설치된 iPhone 시뮬레이터를 선택한 뒤 **⌘R**로 실행합니다. 터미널에서 `xcodebuild`를 사용하는 경우에도 Xcode 정식판은 필요합니다.

## 서버 연결

로그인 화면 하단 또는 설정 탭에서 서버 주소를 바꿀 수 있습니다.

| 실행 환경 | 서버 주소 |
|---|---|
| 저장소 기본 설정 | `https://posefeedback.duckdns.org` |
| 시뮬레이터 → 같은 Mac의 백엔드 | `http://localhost:8000` |
| 실제 iPhone → 같은 Wi-Fi의 Mac | `http://<Mac의 LAN IP>:8000` |
| 별도 배포 서버 | 해당 서버의 HTTPS 주소 |

기본 주소는 설정값이며 현재 서버 가동 상태를 보장하지 않습니다. 연결이 안 되면 서버의 `/health`부터 확인합니다.

실제 iPhone에서 `localhost`는 Mac이 아닌 iPhone 자신입니다. Mac의 Python 서버에 연결하려면 저장소 루트에서 다음과 같이 실행합니다.

```bash
./venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
```

앱의 로컬 네트워크 접근 권한과 Mac의 방화벽 설정도 확인합니다. `project.yml`에는 로컬 네트워크 접근 및 카메라·마이크 권한 설명이 포함돼 있습니다.

## 실제 iPhone에 설치

1. iPhone을 Mac에 연결하고 기기의 컴퓨터 신뢰 요청을 처리합니다.
2. Xcode의 **Signing & Capabilities**에서 사용할 개발 Team을 선택합니다. Bundle Identifier 충돌이 있으면 자신의 식별자로 변경합니다.
3. 실행 대상으로 연결된 iPhone을 선택하고 **⌘R**로 빌드·설치합니다.
4. 기기에서 개발자 모드 또는 개발자 앱 신뢰를 요구하면 해당 안내를 완료한 뒤 다시 실행합니다.

빌드 성공과 앱 실행 성공은 다릅니다. 설치 후 실행이 막히면 Xcode의 실행 오류를 확인합니다. `Developer App Certificate is not trusted` 오류라면 iPhone의 **설정 → 일반 → VPN 및 기기 관리**에서 해당 개발자 앱을 신뢰한 뒤 다시 실행합니다.

## 사용 흐름

1. 서버 주소를 확인하고 회원가입 또는 로그인합니다.
2. **분석** 탭에서 스쿼트·런지·사이드 레터럴 레이즈 중 운동을 선택합니다.
3. 촬영 가이드에서 방향과 구도를 확인하고, 직접 촬영하거나 앨범 영상을 선택합니다.
4. **분석하기**를 누르고 업로드 진행률과 결과 대기 상태를 확인합니다.
5. 결과의 점수·방향별 반복 횟수·우선 교정 항목을 읽습니다. 주요 문제를 열어 모범 자세와 비교하고 0.5배속으로 살펴볼 수 있습니다.
6. **기록** 탭에서 날짜별 결과와 운동별 점수·항목별 변화를 확인합니다.

영상은 업로드 전에 540p로 압축되며, 60초를 초과하면 선택 단계에서 거부됩니다. 로그인한 분석 결과는 서버에 저장되지만 반복을 하나도 인식하지 못한 결과는 저장되지 않습니다.

시뮬레이터의 사진 보관함에 테스트 영상을 넣으려면 `data/raw/user_squat_side_raw.mp4` 같은 파일을 시뮬레이터 창으로 드래그합니다. 실제 촬영은 iPhone에서 확인합니다.

## 촬영 가이드와 오류 처리

- 가이드 영상은 앱에 설정된 서버의 `/guides/{운동}-{방향}.mp4`를 사용합니다. 방향 전환·닫기 시 재생이 중지됩니다.
- Uvicorn만 실행한 로컬 서버에는 `/guides/`가 없으므로, 가이드 재생에는 정적 파일 제공 구성이 별도로 필요합니다.
- 업로드 중에는 실제 전송률을, 업로드 후에는 경과 시간과 대기 상태를 표시합니다.
- 분석 실패 시 선택한 영상을 유지합니다. 재시도 가능한 오류에는 재시도 버튼을 제공하고, 시간 초과 시에는 기록부터 확인하도록 안내합니다.
- 설정 탭에서 서버 변경, 로그아웃, 회원 탈퇴를 할 수 있습니다.

## 테스트

Xcode에서 `PoseFeedback` 스킴을 선택하고 **⌘U**로 단위 테스트와 UI 테스트를 실행합니다.

분석 UI 테스트는 DEBUG 전용 로컬 영상·응답 fixture를 사용합니다. 가이드 통합 테스트는 배포 서버의 공개 영상을 읽으므로 네트워크와 서버 상태에 영향을 받습니다. Release 빌드에는 DEBUG 전용 미리보기 진입점과 fixture가 포함되지 않습니다.

## 주요 파일

| 파일 | 역할 |
|---|---|
| `project.yml` | XcodeGen 설정, iOS 최소 버전, 권한·빌드·테스트 대상 |
| `PoseFeedback/PoseFeedbackApp.swift`, `PoseFeedback/AppState.swift` | 앱 진입점, 로그인 상태·서버 주소 |
| `PoseFeedback/AuthView.swift`, `PoseFeedback/Keychain.swift` | 로그인·회원가입, 토큰 보관 |
| `PoseFeedback/ContentView.swift`, `PoseFeedback/CameraRecorderView.swift` | 운동·영상 선택과 촬영 |
| `PoseFeedback/AnalysisExperience.swift` | 촬영 가이드·분석 상태와 오류 표시 |
| `PoseFeedback/ResultsView.swift`, `PoseFeedback/IssueViews.swift` | 결과 요약·교정 항목·자세 비교 |
| `PoseFeedback/HistoryView.swift`, `PoseFeedback/ProgressChartView.swift` | 기록·캘린더·변화 추이 |
| `PoseFeedback/APIClient.swift`, `PoseFeedback/Models.swift` | API 통신과 응답 모델 |
| `PoseFeedback/VideoCompressor.swift` | 업로드 전 압축과 길이 제한 |
| `PoseFeedbackTests/`, `PoseFeedbackUITests/` | 단위·UI 테스트 |
