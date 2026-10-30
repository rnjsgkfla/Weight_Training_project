#if DEBUG
import Foundation

/// 오프라인 UI 검증 전용 예시. Release 빌드에는 포함되지 않는다.
enum ExperienceFixtures {
    static let session: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [PreviewAnalysisProtocol.self]
        return URLSession(configuration: configuration)
    }()
    static let result: AnalyzeResponse = {
        let good = FeedbackItem(key: "good", label: "양호", detail: "", ok: true,
                                refImage: nil, userImage: nil, view: "측면", rep: 1,
                                featureName: nil, phase: nil, timeSec: nil, refVal: nil,
                                userVal: nil, dev: nil, unit: nil, message: "기준과 큰 차이 없음")
        let issue = Issue(key: "front.valgus", view: "front", viewKr: "정면", feature: "valgus",
                          name: "무릎 모임", unit: "", headline: "무릎이 안쪽으로 모입니다",
                          advice: "무릎이 발끝 방향을 향하도록 해보세요.", reps: [2, 3, 5],
                          totalReps: 5, severity: 1.5, rep: 3, phase: "하강", timeSec: 8.2,
                          refVal: 1, userVal: 0.7, thumbRef: nil, thumbUser: nil, clip: [])
        let other = Issue(key: "side.trunk", view: "side", viewKr: "측면", feature: "trunk",
                          name: "상체 기울기", unit: "°", headline: "상체가 과도하게 앞으로 숙여집니다",
                          advice: nil, reps: [2], totalReps: 5, severity: 1.2, rep: 2,
                          phase: "최저", timeSec: 5, refVal: 20, userVal: 35,
                          thumbRef: nil, thumbUser: nil, clip: [])
        return AnalyzeResponse(exercise: "squat", summary: "UI 테스트 예시", items: [good],
                               issues: [issue, other], goodPoints: ["골반 수평", "스탠스 너비"],
                               stats: SessionStats(score: 72, scoreDetail: nil,
                                                   repCount: ["side": 5, "front": 5], reps: [], warnings: []),
                               sessionId: nil)
    }()
}

/// 실제 서버·계정에 접근하지 않고 최초 실패 → 수동 재시도를 검증한다.
private final class PreviewAnalysisProtocol: URLProtocol, @unchecked Sendable {
    private static let lock = NSLock()
    private static var attempts = 0
    private var work: DispatchWorkItem?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lock.lock()
        Self.attempts += 1
        let attempt = Self.attempts
        Self.lock.unlock()
        let work = DispatchWorkItem { [weak self] in
            guard let self else { return }
            if attempt == 1 {
                self.client?.urlProtocol(self, didFailWithError: URLError(.timedOut))
            } else {
                let response = HTTPURLResponse(url: self.request.url!, statusCode: 200,
                                               httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
                self.client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
                self.client?.urlProtocol(self, didLoad: try! JSONEncoder().encode(ExperienceFixtures.result))
                self.client?.urlProtocolDidFinishLoading(self)
            }
        }
        self.work = work
        DispatchQueue.global().asyncAfter(deadline: .now() + 3, execute: work)
    }

    override func stopLoading() { work?.cancel() }
}
#endif
