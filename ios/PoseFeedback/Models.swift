import Foundation

/// /analyze 응답의 개별 피드백 항목 (api.py FeedbackItem 과 1:1)
struct FeedbackItem: Codable, Identifiable {
    let key: String
    let label: String
    let detail: String
    let ok: Bool
    let refImage: String?
    let userImage: String?

    var id: String { key }

    enum CodingKeys: String, CodingKey {
        case key, label, detail, ok
        case refImage = "ref_image"
        case userImage = "user_image"
    }
}

/// /analyze 전체 응답 (api.py AnalyzeResponse 와 1:1)
struct AnalyzeResponse: Codable {
    let exercise: String
    let summary: String
    let items: [FeedbackItem]
}
