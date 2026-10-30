import XCTest
@testable import PoseFeedback

final class AnalysisFailureTests: XCTestCase {
    func testTimeoutWarnsAboutAlreadySavedResultBeforeRetry() {
        let failure = AnalysisFailure.describe(URLError(.timedOut))
        XCTAssertTrue(failure.canRetry)
        XCTAssertTrue(failure.message.contains("기록 탭"))
        XCTAssertTrue(failure.message.contains("저장됐을 수"))
    }

    func testOfflineCanRetryWithoutSelectingVideoAgain() {
        let failure = AnalysisFailure.describe(URLError(.notConnectedToInternet))
        XCTAssertTrue(failure.canRetry)
        XCTAssertTrue(failure.message.contains("같은 영상"))
    }

    func testInvalidVideoDoesNotEncourageUnchangedRetry() {
        for code in [400, 413, 422] {
            let failure = AnalysisFailure.describe(APIError.server(code, "영상을 다시 선택하세요"))
            XCTAssertFalse(failure.canRetry)
            XCTAssertEqual(failure.message, "영상을 다시 선택하세요")
        }
    }

    func testBusyServerAllowsManualRetry() {
        for code in [429, 500, 502, 503, 504] {
            XCTAssertTrue(AnalysisFailure.describe(APIError.server(code, "서버 오류")).canRetry)
        }
    }

    func testAuthenticationAndCertificateErrorsDoNotSuggestRetry() {
        XCTAssertFalse(AnalysisFailure.describe(APIError.unauthorized).canRetry)
        XCTAssertFalse(AnalysisFailure.describe(APIError.invalidURL).canRetry)
        XCTAssertFalse(AnalysisFailure.describe(URLError(.serverCertificateUntrusted)).canRetry)
    }

    func testMalformedResponsePointsToHistoryWithoutResubmitting() {
        let failure = AnalysisFailure.describe(APIError.invalidResponse)
        XCTAssertFalse(failure.canRetry)
        XCTAssertTrue(failure.message.contains("기록 탭"))
    }
}
