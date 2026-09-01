import Foundation

enum APIError: LocalizedError {
    case server(Int, String)
    case invalidResponse

    var errorDescription: String? {
        switch self {
        case .server(_, let detail): return detail
        case .invalidResponse: return "서버 응답을 해석할 수 없습니다."
        }
    }
}

/// 백엔드(FastAPI /analyze) 호출 클라이언트.
/// 시뮬레이터는 맥의 localhost 에 바로 접속된다. 실기기/외부에서 테스트하려면
/// baseURL 을 LAN IP(http://192.168.x.x:8000) 또는 터널 URL 로 바꾼다.
struct APIClient {
    var baseURL = "http://localhost:8000"

    func analyze(exercise: String, sideVideo: Data?, frontVideo: Data?) async throws -> AnalyzeResponse {
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: URL(string: "\(baseURL)/analyze")!)
        request.httpMethod = "POST"
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

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard http.statusCode == 200 else {
            // FastAPI 오류는 {"detail": "..."} 형식
            let detail = (try? JSONDecoder().decode([String: String].self, from: data))?["detail"]
                ?? "오류가 발생했습니다 (\(http.statusCode))"
            throw APIError.server(http.statusCode, detail)
        }
        return try JSONDecoder().decode(AnalyzeResponse.self, from: data)
    }
}
