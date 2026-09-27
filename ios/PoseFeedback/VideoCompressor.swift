import AVFoundation

enum VideoError: LocalizedError {
    case tooLong(Double)
    case unreadable

    var errorDescription: String? {
        switch self {
        case .tooLong(let sec):
            return "\(Int(sec))초 영상이에요. \(Int(VideoCompressor.maxDuration))초 이하로 잘라서 올려주세요."
        case .unreadable:
            return "영상을 불러오지 못했어요. 다른 영상을 선택해 주세요."
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

    /// 영상 파일(src)을 압축해 업로드할 Data 를 돌려준다. 길이부터 확인해 긴 영상은 바로 거부한다.
    static func prepare(_ src: URL) async throws -> Data {
        let asset = AVURLAsset(url: src)
        guard let duration = try? await asset.load(.duration).seconds, duration > 0 else {
            throw VideoError.unreadable
        }
        guard duration <= maxDuration else { throw VideoError.tooLong(duration) }

        let dst = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".mp4")
        defer { try? FileManager.default.removeItem(at: dst) }
        guard let session = AVAssetExportSession(asset: asset, presetName: AVAssetExportPreset960x540) else {
            return try Data(contentsOf: src)  // 압축할 수 없는 형식이면 원본 그대로
        }
        if #available(iOS 18, *) {
            try await session.export(to: dst, as: .mp4)
        } else {
            session.outputURL = dst
            session.outputFileType = .mp4
            await session.export()
            if let error = session.error { throw error }
        }
        // 원본이 이미 더 작으면(이미 압축된 영상) 원본을 보낸다
        let srcSize = (try? src.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? .max
        let dstSize = (try? dst.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? .max
        return try Data(contentsOf: dstSize < srcSize ? dst : src)
    }
}
