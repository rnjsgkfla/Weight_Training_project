import AVFoundation

enum VideoError: LocalizedError {
    case tooLong(Double)

    var errorDescription: String? {
        switch self {
        case .tooLong(let sec):
            return "영상이 너무 길어요 (\(Int(sec))초). \(Int(VideoCompressor.maxDuration))초 이하로 잘라서 올려주세요. 5~10회 반복이면 충분해요."
        }
    }
}

/// 업로드 전 영상을 540p 로 줄인다.
/// 서버는 어차피 가로 600px 로 줄여 분석하므로 정확도 손해 없이 업로드 용량·시간만 줄어든다.
/// 실측: 아이폰 1080p 원본 16초 33MB → 540p 10MB (720p 는 16MB).
///       샘플 스쿼트·사이드 레터럴 레이즈를 540p 로 분석해도 반복 수·점수·지적 항목 동일
///       (ratio 차이 스쿼트 0.07, 사레레 0.14 이내).
enum VideoCompressor {
    static let maxDuration: Double = 60

    static func prepare(_ data: Data) async throws -> Data {
        let dir = FileManager.default.temporaryDirectory
        let src = dir.appendingPathComponent(UUID().uuidString + ".mp4")
        let dst = dir.appendingPathComponent(UUID().uuidString + ".mp4")
        try data.write(to: src)
        defer {
            try? FileManager.default.removeItem(at: src)
            try? FileManager.default.removeItem(at: dst)
        }

        let asset = AVURLAsset(url: src)
        let duration = try await asset.load(.duration).seconds
        guard duration <= maxDuration else { throw VideoError.tooLong(duration) }

        guard let session = AVAssetExportSession(asset: asset, presetName: AVAssetExportPreset960x540) else {
            return data  // 압축할 수 없는 형식이면 원본 그대로
        }
        if #available(iOS 18, *) {
            try await session.export(to: dst, as: .mp4)
        } else {
            session.outputURL = dst
            session.outputFileType = .mp4
            await session.export()
            if let error = session.error { throw error }
        }
        let compressed = try Data(contentsOf: dst)
        return compressed.count < data.count ? compressed : data
    }
}
