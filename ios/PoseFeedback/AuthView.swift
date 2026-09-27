import SwiftUI

/// 로그인 / 회원가입 화면. 로그인 전에 서버 주소도 여기서 바꿀 수 있다.
struct AuthView: View {
    @Environment(AppState.self) private var appState

    @State private var isSignup = false
    @State private var email = ""
    @State private var password = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showServer = false

    private var canSubmit: Bool {
        email.contains("@") && password.count >= 8 && !isLoading
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    VStack(spacing: 10) {
                        Image(systemName: "figure.strengthtraining.traditional")
                            .font(.system(size: 46, weight: .semibold))
                            .foregroundStyle(Color.brand)
                        Text("운동 자세 피드백").font(.largeTitle).bold()
                        Text("로그인하면 운동 기록과 피드백이 저장돼요")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                    .padding(.top, 40)

                    Picker("", selection: $isSignup) {
                        Text("로그인").tag(false)
                        Text("회원가입").tag(true)
                    }
                    .pickerStyle(.segmented)

                    VStack(spacing: 12) {
                        TextField("이메일", text: $email)
                            .keyboardType(.emailAddress)
                            .textContentType(.emailAddress)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .padding(14)
                            .background(Color(.secondarySystemGroupedBackground))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        SecureField(isSignup ? "비밀번호 (8자 이상)" : "비밀번호", text: $password)
                            .textContentType(isSignup ? .newPassword : .password)
                            .padding(14)
                            .background(Color(.secondarySystemGroupedBackground))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }

                    if let errorMessage {
                        Label(errorMessage, systemImage: "exclamationmark.circle.fill")
                            .font(.subheadline)
                            .foregroundStyle(.red)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    Button { Task { await submit() } } label: {
                        Group {
                            if isLoading { ProgressView().tint(.white) }
                            else { Text(isSignup ? "가입하고 시작하기" : "로그인") }
                        }
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(canSubmit ? Color.brand : Color.gray.opacity(0.4))
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                    }
                    .disabled(!canSubmit)

                    Button { showServer = true } label: {
                        Label("서버: \(appState.serverURL)", systemImage: "server.rack")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(20)
            }
            .background(Color(.systemGroupedBackground))
            .sheet(isPresented: $showServer) { ServerSettingsSheet() }
            .onChange(of: isSignup) { errorMessage = nil }
        }
        .tint(.brand)
    }

    private func submit() async {
        isLoading = true
        errorMessage = nil
        do {
            try await appState.login(email: email, password: password, signup: isSignup)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

/// 서버 주소 입력 시트 (로그인 화면·설정 화면 공용)
struct ServerSettingsSheet: View {
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss
    @State private var draft = ""

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField(AppState.defaultServerURL, text: $draft)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } header: {
                    Text("서버 주소")
                } footer: {
                    Text("시뮬레이터: \(AppState.defaultServerURL)\n배포 서버: https://도메인")
                }
            }
            .navigationTitle("서버 설정")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("취소") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("저장") {
                        appState.setServerURL(draft)
                        dismiss()
                    }
                }
            }
            .onAppear { draft = appState.serverURL }
        }
        .presentationDetents([.medium])
    }
}
