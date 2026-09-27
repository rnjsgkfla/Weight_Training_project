import Foundation

enum APIError: LocalizedError {
    case server(Int, String)
    case invalidResponse
    case invalidURL
    /// 로그인 토큰이 만료·무효 (다시 로그인 필요)
    case unauthorized

    var errorDescription: String? {
        switch self {
        case .server(_, let detail): return detail
        case .invalidResponse: return "서버 응답을 해석할 수 없습니다."
        case .invalidURL: return "서버 주소가 올바르지 않습니다. 설정에서 확인해 주세요."
        case .unauthorized: return "로그인이 만료됐어요. 다시 로그인해 주세요."
        }
    }
}

/// 백엔드(FastAPI) 호출 클라이언트.
/// 서버 주소는 설정 화면에서 바꾼다 (시뮬레이터: http://localhost:8000, 배포 서버: https://...).
struct APIClient {
    var baseURL: String
    /// 로그인 토큰. 있으면 Authorization: Bearer 헤더로 보낸다.
    var token: String?

    // MARK: - 계정

    func signup(email: String, password: String) async throws -> String {
        let res: TokenResponse = try await send(jsonRequest("POST", "/auth/signup",
                                                            body: ["email": email, "password": password]))
        return res.accessToken
    }

    func login(email: String, password: String) async throws -> String {
        let res: TokenResponse = try await send(jsonRequest("POST", "/auth/login",
                                                            body: ["email": email, "password": password]))
        return res.accessToken
    }

    func deleteAccount() async throws {
        try await sendNoContent(request("DELETE", "/me"))
    }

    // MARK: - 분석

    func analyze(exercise: String, sideVideo: Data?, frontVideo: Data?) async throws -> AnalyzeResponse {
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = try request("POST", "/analyze")
        request.timeoutInterval = 180
        request.setValue("multipart/form-data; boundary=\(boundary)",
                         forHTTPHeaderField: "Content-Type")

        var body = Data()
        func appendString(_ s: String) { body.append(s.data(using: .utf8)!) }

        // exercise 필드
        appendString("--\(boundary)\r\n")
        appendString("Content-Disposition: form-data; name=\"exercise\"\r\n\r\n")
        appendString("\(exercise)\r\n")

        // 영상 파일 필드
        func appendVideo(_ name: String, _ data: Data) {
            appendString("--\(boundary)\r\n")
            appendString("Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(name).mp4\"\r\n")
            appendString("Content-Type: video/mp4\r\n\r\n")
            body.append(data)
            appendString("\r\n")
        }
        if let sideVideo { appendVideo("side_video", sideVideo) }
        if let frontVideo { appendVideo("front_video", frontVideo) }
        appendString("--\(boundary)--\r\n")

        request.httpBody = body
        return try await send(request)
    }

    // MARK: - 히스토리

    func sessions(limit: Int = 200) async throws -> [SessionSummary] {
        try await send(request("GET", "/sessions", query: [URLQueryItem(name: "limit", value: "\(limit)")]))
    }

    func session(id: Int) async throws -> AnalyzeResponse {
        try await send(request("GET", "/sessions/\(id)"))
    }

    func deleteSession(id: Int) async throws {
        try await sendNoContent(request("DELETE", "/sessions/\(id)"))
    }

    func progress(exercise: String) async throws -> ProgressResponse {
        try await send(request("GET", "/progress/\(exercise)"))
    }

    // MARK: - 공통

    private func request(_ method: String, _ path: String, query: [URLQueryItem] = []) throws -> URLRequest {
        guard var comps = URLComponents(string: baseURL + path), comps.host != nil else {
            throw APIError.invalidURL
        }
        if !query.isEmpty { comps.queryItems = query }
        guard let url = comps.url else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = 30
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        return req
    }

    private func jsonRequest(_ method: String, _ path: String, body: [String: String]) throws -> URLRequest {
        var req = try request(method, path)
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(body)
        return req
    }

    private func send<T: Decodable>(_ request: URLRequest) async throws -> T {
        let data = try await perform(request)
        do {
            return try Self.decoder.decode(T.self, from: data)
        } catch {
            throw APIError.invalidResponse
        }
    }

    private func sendNoContent(_ request: URLRequest) async throws {
        _ = try await perform(request)
    }

    private func perform(_ request: URLRequest) async throws -> Data {
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            // 토큰을 보냈는데 401 = 만료·무효 토큰 (로그인 실패의 401 은 서버 문구를 그대로 보여준다)
            if http.statusCode == 401 && token != nil { throw APIError.unauthorized }
            // FastAPI 오류는 {"detail": "..."} 형식 (입력 검증 실패 422 는 detail 이 목록)
            let detail = (try? JSONDecoder().decode([String: String].self, from: data))?["detail"]
                ?? (http.statusCode == 422 ? "입력값을 확인해 주세요." : "오류가 발생했습니다 (\(http.statusCode))")
            throw APIError.server(http.statusCode, detail)
        }
        return data
    }

    /// 서버 시각은 ISO 8601 (소수점 초 6자리 + 시간대) — 소수점 유무 모두 파싱한다
    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .custom { decoder in
            let s = try decoder.singleValueContainer().decode(String.self)
            if let date = try? Date(s, strategy: Date.ISO8601FormatStyle(includingFractionalSeconds: true)) {
                return date
            }
            return try Date(s, strategy: .iso8601)
        }
        return d
    }()
}
