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

/// /analyze 전체 응답 (api.py AnalyzeResponse 와 1:1)
struct AnalyzeResponse: Codable {
    let exercise: String
    let summary: String
    let items: [FeedbackItem]
}
