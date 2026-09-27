import Foundation
import Observation

/// 앱 전역 상태: 로그인 토큰·서버 주소를 들고 있고, API 호출을 대신해 준다.
/// 토큰이 만료(401)되면 자동으로 로그아웃해 로그인 화면으로 돌아간다.
@MainActor
@Observable
final class AppState {
    private static let tokenKey = "accessToken"
    private static let emailKey = "email"
    private static let serverKey = "serverURL"
    static let defaultServerURL = "http://localhost:8000"

    private(set) var token: String? = Keychain.load(AppState.tokenKey)
    private(set) var email: String? = UserDefaults.standard.string(forKey: AppState.emailKey)

    /// 백엔드 주소 (시뮬레이터 기본값 localhost, 배포 후엔 https://도메인)
    var serverURL: String = UserDefaults.standard.string(forKey: AppState.serverKey) ?? AppState.defaultServerURL {
        didSet { UserDefaults.standard.set(serverURL, forKey: AppState.serverKey) }
    }

    /// 새 분석이 저장될 때마다 올려서 기록 탭이 다시 불러오게 한다
    var historyVersion = 0

    var isLoggedIn: Bool { token != nil }
    var api: APIClient { APIClient(baseURL: serverURL, token: token) }

    func setServerURL(_ raw: String) {
        var s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        while s.hasSuffix("/") { s.removeLast() }
        serverURL = s.isEmpty ? AppState.defaultServerURL : s
    }

    func login(email: String, password: String, signup: Bool) async throws {
        let email = email.trimmingCharacters(in: .whitespaces).lowercased()
        let client = APIClient(baseURL: serverURL, token: nil)
        let token = signup ? try await client.signup(email: email, password: password)
                           : try await client.login(email: email, password: password)
        Keychain.save(token, for: AppState.tokenKey)
        UserDefaults.standard.set(email, forKey: AppState.emailKey)
        self.token = token
        self.email = email
    }

    func logout() {
        Keychain.delete(AppState.tokenKey)
        UserDefaults.standard.removeObject(forKey: AppState.emailKey)
        token = nil
        email = nil
    }

    func deleteAccount() async throws {
        try await run { try await $0.deleteAccount() }
        logout()
    }

    /// 로그인 상태의 API 호출. 토큰이 만료됐으면 로그아웃한 뒤 오류를 그대로 던진다.
    func run<T>(_ operation: (APIClient) async throws -> T) async throws -> T {
        do {
            return try await operation(api)
        } catch APIError.unauthorized {
            logout()
            throw APIError.unauthorized
        }
    }
}
