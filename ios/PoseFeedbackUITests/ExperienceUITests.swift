import XCTest

final class ExperienceUITests: XCTestCase {
    func testTimeoutKeepsVideoAndManualRetrySucceeds() {
        let app = XCUIApplication()
        app.launchArguments = ["--preview-retry"]
        app.launch()
        XCTAssertTrue(app.buttons["analysis.submit"].isEnabled)
        app.buttons["analysis.submit"].tap()
        XCTAssertFalse(app.buttons["analysis.submit"].isEnabled)
        XCTAssertFalse(app.buttons["exercise.lunge"].isEnabled)
        XCTAssertTrue(app.buttons["analysis.retry"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["선택한 영상은 그대로 남아 있어요."].exists)
        saveScreenshot("retry-after-timeout")
        app.buttons["analysis.retry"].tap()
        XCTAssertTrue(app.staticTexts["72"].waitForExistence(timeout: 10))
    }

    func testSwitchingExerciseClearsPreviouslySelectedVideo() {
        let app = XCUIApplication()
        app.launchArguments = ["--preview-retry"]
        app.launch()
        XCTAssertTrue(app.buttons["analysis.submit"].isEnabled)
        app.buttons["exercise.lunge"].tap()
        XCTAssertFalse(app.buttons["analysis.submit"].isEnabled)
    }

    func testExerciseSpecificGuideAndEmptySubmission() {
        let app = XCUIApplication()
        app.launchArguments = ["--preview-analysis"]
        app.launch()
        XCTAssertFalse(app.buttons["analysis.submit"].isEnabled)
        app.buttons["exercise.lateral_raise"].tap()
        app.buttons["capture.guide"].tap()
        XCTAssertTrue(app.staticTexts["양팔을 벌려도 손끝이 보이게"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.segmentedControls["촬영 방향"].exists)
        saveScreenshot("lateral-raise-guide")
        app.buttons["완료"].tap()
        app.buttons["exercise.lunge"].tap()
        app.buttons["capture.guide"].tap()
        XCTAssertTrue(app.segmentedControls.buttons["측면"].waitForExistence(timeout: 5))
        app.segmentedControls.buttons["정면"].tap()
        app.swipeUp()
        XCTAssertTrue(app.staticTexts["카메라를 몸의 정면에 놓고, 양쪽 어깨와 골반이 보이게 찍어주세요."].exists)
    }

    func testLiveGuideVideoLoadsFromAWS() {
        let app = XCUIApplication()
        app.launchArguments = ["--preview-analysis"]
        app.launch()
        app.buttons["capture.guide"].tap()
        XCTAssertTrue(app.staticTexts["guide.ready"].waitForExistence(timeout: 30))
        app.segmentedControls.buttons["정면"].tap()
        XCTAssertTrue(app.staticTexts["guide.ready"].waitForExistence(timeout: 30))
        saveScreenshot("aws-guide-video")
    }

    func testPriorityResultAndDetailNavigation() {
        let app = XCUIApplication()
        app.launchArguments = ["--preview-results"]
        app.launch()
        XCTAssertTrue(app.staticTexts["72"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["측면 · 5회 분석"].exists)
        XCTAssertTrue(app.staticTexts["정면 · 5회 분석"].exists)
        XCTAssertFalse(app.staticTexts["상체가 과도하게 앞으로 숙여집니다"].exists)
        saveScreenshot("result-overview")
        app.staticTexts["모범 자세와 비교하기"].tap()
        XCTAssertTrue(app.navigationBars["무릎 모임"].waitForExistence(timeout: 5))
    }

    func testWaitingDoesNotShowInventedAnalysisPercentage() {
        let app = XCUIApplication()
        app.launchArguments = ["--preview-waiting"]
        app.launch()
        XCTAssertTrue(app.staticTexts["분석 결과를 기다리고 있어요"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.staticTexts["영상 전송 100%"].exists)
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "경과 1분")).firstMatch.exists)
        saveScreenshot("analysis-waiting")
    }

    private func saveScreenshot(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
