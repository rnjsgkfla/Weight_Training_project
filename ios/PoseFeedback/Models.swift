import Foundation

/// /analyze 응답의 개별 피드백 항목 (api.py FeedbackItem 과 1:1)
struct FeedbackItem: Codable, Identifiable {
    let key: String
    let label: String
    let detail: String
    let ok: Bool
    let refImage: String?
    let userImage: String?

    // 구조화 필드 (앱 비교 화면용, 양호 항목은 수치가 없어 nil 일 수 있음)
    let view: String?
    let rep: Int?
    let featureName: String?
    let phase: String?
    let timeSec: Double?
    let refVal: Double?
    let userVal: Double?
    let dev: Double?
    let unit: String?
    let message: String?

    var id: String { key }

    enum CodingKeys: String, CodingKey {
        case key, label, detail, ok, view, rep, phase, unit, message, dev
        case refImage = "ref_image"
        case userImage = "user_image"
        case featureName = "feature_name"
        case timeSec = "time_sec"
        case refVal = "ref_val"
        case userVal = "user_val"
    }
}

/// /analyze 전체 응답 (schemas.py AnalyzeResponse 와 1:1).
/// 기록 상세(/sessions/{id})도 같은 모양이라 그대로 디코딩해 ResultsView 를 재사용한다.
struct AnalyzeResponse: Codable {
    let exercise: String
    let summary: String
    let items: [FeedbackItem]
    let stats: SessionStats?
    let sessionId: Int?

    enum CodingKeys: String, CodingKey {
        case exercise, summary, items, stats
        case sessionId = "session_id"
    }
}

// MARK: - 통계 (점수·회차별 측정값)

struct RepMetric: Codable {
    let feature: String
    let name: String
    let unit: String
    let dev: Double
    let tol: Double
    /// 벗어난 정도 / 허용오차 (1 초과면 허용오차 밖)
    let ratio: Double
    let fault: Bool
}

struct RepStats: Codable {
    let view: String
    let rep: Int
    let faultCount: Int
    let metrics: [RepMetric]

    enum CodingKeys: String, CodingKey {
        case view, rep, metrics
        case faultCount = "fault_count"
    }
}

struct SessionStats: Codable {
    let score: Int?
    let repCount: [String: Int]
    let reps: [RepStats]

    enum CodingKeys: String, CodingKey {
        case score, reps
        case repCount = "rep_count"
    }
}

// MARK: - 계정

struct TokenResponse: Codable {
    let accessToken: String

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
    }
}

// MARK: - 히스토리

/// /sessions 목록의 한 줄
struct SessionSummary: Codable, Identifiable {
    let id: Int
    let exercise: String
    let createdAt: Date
    let score: Int?
    let repCount: [String: Int]
    let topFaults: [String]

    enum CodingKeys: String, CodingKey {
        case id, exercise, score
        case createdAt = "created_at"
        case repCount = "rep_count"
        case topFaults = "top_faults"
    }

    var totalReps: Int { repCount.values.reduce(0, +) }
}

struct FeatureProgress: Codable {
    let view: String
    let feature: String
    let name: String
    /// 회차 평균 ratio (낮을수록 좋음, 1 이하면 허용 범위)
    let avgRatio: Double
    let faultRate: Double

    enum CodingKeys: String, CodingKey {
        case view, feature, name
        case avgRatio = "avg_ratio"
        case faultRate = "fault_rate"
    }

    /// 뷰가 달라도 이름이 같은 특징이 있을 수 있어 뷰까지 포함한 식별자
    var id: String { "\(view).\(feature)" }
    var label: String { "\(view == "side" ? "측면" : "정면") · \(name)" }
}

struct ProgressPoint: Codable, Identifiable {
    let sessionId: Int
    let createdAt: Date
    let score: Int?
    let features: [FeatureProgress]

    enum CodingKeys: String, CodingKey {
        case score, features
        case sessionId = "session_id"
        case createdAt = "created_at"
    }

    var id: Int { sessionId }
}

struct ProgressResponse: Codable {
    let exercise: String
    let points: [ProgressPoint]
}

// MARK: - 운동 목록

enum Exercises {
    /// (키, 이름, SF Symbol). 서버 api.py REFERENCE 의 키와 같다.
    static let all: [(key: String, name: String, icon: String)] = [
        ("squat", "스쿼트", "figure.strengthtraining.traditional"),
        ("lunge", "런지", "figure.strengthtraining.functional"),
        ("lateral_raise", "사이드 레터럴 레이즈", "figure.arms.open"),
    ]

    static func name(_ key: String) -> String {
        all.first { $0.key == key }?.name ?? key
    }

    static func icon(_ key: String) -> String {
        all.first { $0.key == key }?.icon ?? "figure.walk"
    }
}
