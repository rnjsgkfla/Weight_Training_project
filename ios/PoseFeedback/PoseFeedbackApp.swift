import SwiftUI

@main
struct PoseFeedbackApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(appState)
        }
    }
}

/// 로그인 전: 로그인 화면 / 로그인 후: 분석·기록·설정 탭
struct RootView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        if appState.isLoggedIn {
            TabView {
                ContentView()
                    .tabItem { Label("분석", systemImage: "figure.strengthtraining.traditional") }
                HistoryView()
                    .tabItem { Label("기록", systemImage: "calendar") }
                SettingsView()
                    .tabItem { Label("설정", systemImage: "gearshape") }
            }
            .tint(.brand)
        } else {
            AuthView()
        }
    }
}
