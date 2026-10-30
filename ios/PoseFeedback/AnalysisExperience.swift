import SwiftUI
import AVKit

/// 재시도가 도움이 되는 오류와 영상/계정 설정을 먼저 고쳐야 하는 오류를 구분한다.
struct AnalysisFailure {
    let title: String
    let message: String
    let canRetry: Bool

    static func describe(_ error: Error) -> AnalysisFailure {
        if let url = error as? URLError {
            switch url.code {
            case .timedOut, .networkConnectionLost:
                return .init(title: "결과를 받지 못했어요",
                             message: "서버에 결과가 저장됐을 수 있어요. 기록 탭을 먼저 확인한 뒤 다시 시도해 주세요.", canRetry: true)
            case .notConnectedToInternet:
                return .init(title: "인터넷 연결을 확인해 주세요",
                             message: "Wi-Fi 또는 모바일 데이터에 연결한 뒤 같은 영상으로 다시 시도할 수 있어요.", canRetry: true)
            case .cannotConnectToHost, .cannotFindHost, .dnsLookupFailed:
                return .init(title: "서버에 연결하지 못했어요",
                             message: "설정의 서버 주소와 인터넷 연결을 확인해 주세요.", canRetry: true)
            default:
                return .init(title: "연결을 확인해 주세요", message: url.localizedDescription, canRetry: false)
            }
        }
        if let api = error as? APIError {
            switch api {
            case .server(let status, let detail):
                if status >= 500 || status == 429 {
                    return .init(title: "잠시 후 다시 시도해 주세요",
                                 message: detail + "\n기록이 이미 저장됐는지 먼저 확인해 주세요.", canRetry: true)
                }
                return .init(title: "영상을 확인해 주세요", message: detail, canRetry: false)
            case .invalidResponse:
                return .init(title: "결과를 표시하지 못했어요",
                             message: "기록 탭에서 결과가 저장됐는지 확인해 주세요. 문제가 계속되면 앱을 업데이트해 주세요.", canRetry: false)
            case .unauthorized, .invalidURL:
                return .init(title: "설정을 확인해 주세요", message: api.localizedDescription, canRetry: false)
            }
        }
        return .init(title: "분석하지 못했어요", message: error.localizedDescription, canRetry: false)
    }
}

struct AnalysisWaitingCard: View {
    let startedAt: Date
    let uploadProgress: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                ProgressView()
                Text(uploadProgress == nil ? "서버에 분석을 요청하고 있어요" :
                     uploadProgress! < 1 ? "영상을 전송하고 있어요" : "분석 결과를 기다리고 있어요")
                    .font(.headline)
            }
            if let progress = uploadProgress, progress < 1 {
                ProgressView(value: progress)
                Text("영상 전송 \(Int(progress * 100))%")
                    .font(.caption.monospacedDigit())
            }
            TimelineView(.periodic(from: startedAt, by: 1)) { context in
                let seconds = max(0, Int(context.date.timeIntervalSince(startedAt)))
                Text("경과 \(seconds / 60)분 \(seconds % 60)초")
                    .font(.subheadline.monospacedDigit()).foregroundStyle(.secondary)
            }
            Text("영상 길이와 서버 상태에 따라 시간이 달라져요. 완료될 때까지 앱을 열어두세요.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Color.brand.opacity(0.08), in: RoundedRectangle(cornerRadius: 16))
        .accessibilityIdentifier("analysis.waiting")
    }
}

struct CaptureGuide: View {
    let exercise: String
    @State var view: String
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    private var isRaise: Bool { exercise == "lateral_raise" }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    if !isRaise {
                        Picker("촬영 방향", selection: $view) {
                            Text("측면").tag("side")
                            Text("정면").tag("front")
                        }
                        .pickerStyle(.segmented)
                    }
                    GuideVideo(url: URL(string: appState.serverURL + "/guides/\(exercise)-\(view).mp4"))
                        .id("\(exercise)-\(view)-\(appState.serverURL)")
                    VStack(spacing: 12) {
                        Image(systemName: isRaise ? "figure.arms.open" : "figure.stand")
                            .font(.system(size: 90, weight: .light))
                            .foregroundStyle(Color.brand)
                            .frame(maxWidth: .infinity, minHeight: 150)
                            .overlay(RoundedRectangle(cornerRadius: 24).strokeBorder(Color.brand.opacity(0.3), style: StrokeStyle(lineWidth: 2, dash: [8])))
                        Text(isRaise ? "양팔을 벌려도 손끝이 보이게" : "머리부터 발끝까지 화면 안에")
                            .font(.headline)
                    }
                    guideRow("camera", "카메라 위치", view == "side"
                             ? "몸의 옆면이 보이도록 카메라를 옆에 놓으세요. 비스듬한 각도는 피해 주세요."
                             : "카메라를 몸의 정면에 놓고, 양쪽 어깨와 골반이 보이게 찍어주세요.")
                    guideRow("viewfinder", "화면에 담을 범위", isRaise
                             ? "머리·골반과 양팔 전체를 담으세요. 팔을 가장 높이 들었을 때도 손목이 잘리지 않아야 해요."
                             : exercise == "lunge"
                             ? "앞발과 뒷발 모두 담으세요. 내려앉거나 다리를 바꿔도 발이 화면 밖으로 나가지 않게 여유를 두세요."
                             : "서 있을 때와 앉았을 때 모두 머리·골반·무릎·발목이 보이게 여유를 두세요.")
                    guideRow("iphone.gen3", "흔들리지 않게", "휴대폰을 고정하고 밝은 곳에서 한 사람만 촬영하세요. 몸이 기구에 가려지지 않게 해주세요.")
                    guideRow("repeat", "촬영 길이", "평소 속도로 5~10회 반복하고, 60초 이내로 촬영하세요. 시작과 끝에는 잠깐 기본 자세를 유지해 주세요.")
                    if !isRaise {
                        Text("한 방향만 올려도 분석할 수 있어요. 정면·측면을 모두 올리면 더 많은 항목을 확인할 수 있어요. 두 영상은 따로 촬영해도 됩니다.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                }
                .padding(20)
            }
            .navigationTitle("\(Exercises.name(exercise)) 촬영 가이드")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("완료") { dismiss() } } }
        }
    }

    private func guideRow(_ icon: String, _ title: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon).foregroundStyle(Color.brand).frame(width: 24)
            VStack(alignment: .leading, spacing: 5) {
                Text(title).font(.headline)
                Text(text).font(.subheadline).foregroundStyle(.secondary)
            }
        }
    }
}

/// Playback is loaded on demand; changing direction or closing the sheet stops it.
private struct GuideVideo: View {
    let url: URL?
    @State private var player: AVPlayer?
    @State private var failure = false
    @State private var attempt = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("기준 자세 영상").font(.headline)
            if failure {
                VStack(spacing: 12) {
                    Text("영상을 불러오지 못했어요. 연결 상태를 확인해 주세요.")
                    Button("영상 다시 불러오기") { attempt += 1 }
                        .accessibilityIdentifier("guide.retry")
                }
                .frame(maxWidth: .infinity, minHeight: 200)
            } else if let player {
                VideoPlayer(player: player)
                    .frame(height: 260)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .accessibilityIdentifier("guide.player")
                Text("재생 버튼을 눌러 기준 자세와 촬영 방향을 확인하세요.")
                    .font(.caption).foregroundStyle(.secondary)
                    .accessibilityIdentifier("guide.ready")
            } else {
                ProgressView("기준 영상을 불러오는 중이에요")
                    .frame(maxWidth: .infinity, minHeight: 200)
            }
        }
        .task(id: attempt) {
            failure = false
            player?.pause()
            player = nil
            guard let url else { failure = true; return }
            do {
                let asset = AVURLAsset(url: url)
                let playable = try await asset.load(.isPlayable)
                try Task.checkCancellation()
                guard playable else { failure = true; return }
                player = AVPlayer(playerItem: AVPlayerItem(asset: asset))
            } catch {
                if !Task.isCancelled { failure = true }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: AVPlayerItem.failedToPlayToEndTimeNotification)) { notification in
            guard let item = notification.object as? AVPlayerItem,
                  item === player?.currentItem else { return }
            player?.pause()
            failure = true
        }
        .onDisappear { player?.pause() }
    }
}
