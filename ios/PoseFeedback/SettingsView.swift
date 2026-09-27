import SwiftUI

/// 설정 탭: 계정·서버 주소·로그아웃·회원 탈퇴
struct SettingsView: View {
    @Environment(AppState.self) private var appState
    @State private var showServer = false
    @State private var confirmDelete = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("계정") {
                    LabeledContent("이메일", value: appState.email ?? "-")
                    Button("로그아웃") { appState.logout() }
                }

                Section("서버") {
                    Button { showServer = true } label: {
                        LabeledContent("주소", value: appState.serverURL)
                    }
                    .foregroundStyle(.primary)
                }

                Section {
                    Button("회원 탈퇴", role: .destructive) { confirmDelete = true }
                        // 버튼에 붙여야 확인 팝오버가 이 버튼을 가리킨다
                        .confirmationDialog("정말 탈퇴할까요?", isPresented: $confirmDelete, titleVisibility: .visible) {
                            Button("탈퇴하고 모든 기록 삭제", role: .destructive) {
                                Task {
                                    do { try await appState.deleteAccount() }
                                    catch { errorMessage = error.localizedDescription }
                                }
                            }
                            Button("취소", role: .cancel) {}
                        }
                } footer: {
                    if let errorMessage {
                        Text(errorMessage).foregroundStyle(.red)
                    } else {
                        Text("탈퇴하면 모든 운동 기록과 피드백 이미지가 삭제되며 되돌릴 수 없어요.")
                    }
                }

                Section("정보") {
                    LabeledContent("버전", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "-")
                }
            }
            .navigationTitle("설정")
            .sheet(isPresented: $showServer) { ServerSettingsSheet() }
        }
    }
}
