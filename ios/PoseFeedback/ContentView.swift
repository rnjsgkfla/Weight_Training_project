import SwiftUI
import PhotosUI
import AVFoundation
import UIKit

struct ContentView: View {
    @Environment(AppState.self) private var appState
    @State private var exercise = "squat"

    // 측면
    @State private var side = VideoSlot()
    @State private var sideItem: PhotosPickerItem?
    @State private var showSideOptions = false
    @State private var showSidePicker = false
    @State private var showSideCamera = false
    // 정면
    @State private var front = VideoSlot()
    @State private var frontItem: PhotosPickerItem?
    @State private var showFrontOptions = false
    @State private var showFrontPicker = false
    @State private var showFrontCamera = false

    @State private var isLoading = false
    @State private var result: AnalyzeResponse?
    @State private var showResults = false
    @State private var failure: AnalysisFailure?
    @State private var showGuide = false
    @State private var startedAt = Date()
    @State private var uploadProgress: Double?
    @State private var requestID = UUID()

    init(initialSide: VideoSlot = VideoSlot()) {
        _side = State(initialValue: initialSide)
    }

    private let exercises = Exercises.all

    /// 운동별로 필요한 영상 뷰 (api.py REFERENCE 와 1:1 — 사이드 레터럴 레이즈는 정면만 쓴다)
    private let exerciseViews: [String: Set<String>] = [
        "squat": ["side", "front"],
        "lunge": ["side", "front"],
        "lateral_raise": ["front"],
    ]
    private var currentViews: Set<String> { exerciseViews[exercise] ?? ["side", "front"] }

    private var isPreparing: Bool { side.isPreparing || front.isPreparing }

    private var canAnalyze: Bool {
        currentViews.contains("side") ? (side.data != nil || front.data != nil) : front.data != nil
    }

    var body: some View {
        NavigationStack {
            ScrollViewReader { scroll in
            ScrollView {
                VStack(spacing: 26) {
                    hero
                        .id("analysis.top")
                    if isLoading {
                        AnalysisWaitingCard(startedAt: startedAt, uploadProgress: uploadProgress)
                    }
                    if let failure { failureCard(failure) }
                    Group {
                        exerciseSection
                        videoSection
                    }
                    .disabled(isLoading)
                }
                .padding(20)
            }
            .onChange(of: isLoading) { _, _ in
                withAnimation { scroll.scrollTo("analysis.top", anchor: .top) }
            }
            .background(Color(.systemGroupedBackground))
            .toolbar(.hidden, for: .navigationBar)
            .safeAreaInset(edge: .bottom) { analyzeBar }
            .navigationDestination(isPresented: $showResults) {
                if let result { ResultsView(response: result) }
            }
            .sheet(isPresented: $showGuide) {
                CaptureGuide(exercise: exercise, view: exercise == "lateral_raise" ? "front" : "side")
            }
            }
        }
        .tint(.brand)
    }

    // MARK: - 히어로

    private var hero: some View {
        VStack(spacing: 10) {
            Image(systemName: "figure.strengthtraining.traditional")
                .font(.system(size: 46, weight: .semibold))
                .foregroundStyle(Color.brand)
            Text("운동 자세 피드백")
                .font(.largeTitle).bold()
            Text("영상을 올리면 모범 자세와 비교해 드려요")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 12)
    }

    // MARK: - 운동 선택

    private var exerciseSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("운동").font(.headline)
            HStack(spacing: 12) {
                ForEach(exercises, id: \.0) { ex in
                    exerciseCard(key: ex.0, title: ex.1, icon: ex.2)
                }
            }
        }
    }

    private func exerciseCard(key: String, title: String, icon: String) -> some View {
        let selected = exercise == key
        return Button {
            guard exercise != key else { return }
            withAnimation(.easeInOut(duration: 0.15)) {
                exercise = key
                // 다른 운동의 영상을 잘못 전송하지 않도록 양쪽을 초기화한다.
                // loadID도 교체되어 이전 비동기 영상 준비 결과는 적용되지 않는다.
                side = VideoSlot()
                front = VideoSlot()
                sideItem = nil
                frontItem = nil
                failure = nil
            }
        } label: {
            VStack(spacing: 8) {
                Image(systemName: icon).font(.title2)
                Text(title)
                    .font(.subheadline).bold()
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                    .minimumScaleFactor(0.8)
            }
            .frame(maxWidth: .infinity, minHeight: 76)
            .padding(.vertical, 12)
            .background(selected ? Color.brand.opacity(0.14) : Color(.secondarySystemGroupedBackground))
            .foregroundStyle(selected ? Color.brand : Color.primary)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(selected ? Color.brand : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("exercise.\(key)")
    }

    // MARK: - 영상 선택

    private var videoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(currentViews.count > 1 ? "영상 (하나 이상)" : "영상").font(.headline)
            Button { showGuide = true } label: {
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: "camera.viewfinder").font(.title2)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("촬영 전에 확인해 주세요").font(.subheadline.bold())
                        Text(exercise == "lateral_raise" ? "정면에서 양팔과 골반까지 · 60초 이내" : "정면 또는 측면 · 전신이 보이게 · 60초 이내")
                            .font(.caption)
                    }
                    Spacer(minLength: 0)
                    Image(systemName: "chevron.right").font(.caption)
                }
                .padding(14)
                .background(Color.brand.opacity(0.08), in: RoundedRectangle(cornerRadius: 14))
            }
            .buttonStyle(.plain)
            .foregroundStyle(Color.brand)
            .accessibilityIdentifier("capture.guide")
            if currentViews.contains("side") {
                videoCard("측면 영상", slot: $side, item: $sideItem,
                          showOptions: $showSideOptions, showPicker: $showSidePicker, showCamera: $showSideCamera)
            }
            if currentViews.contains("front") {
                videoCard("정면 영상", slot: $front, item: $frontItem,
                          showOptions: $showFrontOptions, showPicker: $showFrontPicker, showCamera: $showFrontCamera)
            }
            Text("5~10회 반복한 영상을 선택하세요. 운동 종류를 바꾸면 선택한 영상은 초기화돼요.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func videoCard(_ title: String,
                           slot: Binding<VideoSlot>,
                           item: Binding<PhotosPickerItem?>,
                           showOptions: Binding<Bool>,
                           showPicker: Binding<Bool>,
                           showCamera: Binding<Bool>) -> some View {
        Button { showOptions.wrappedValue = true } label: {
            HStack(spacing: 14) {
                if slot.wrappedValue.isPreparing {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.brand.opacity(0.12))
                        .frame(width: 76, height: 56)
                        .overlay(ProgressView())
                } else if let img = slot.wrappedValue.thumb {
                    Image(uiImage: img)
                        .resizable().scaledToFill()
                        .frame(width: 76, height: 56)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                } else {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.brand.opacity(0.12))
                        .frame(width: 76, height: 56)
                        .overlay(Image(systemName: "plus").font(.title3).foregroundStyle(Color.brand))
                }
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).font(.body).bold().foregroundStyle(.primary)
                    // 오류는 카드 안에 바로 보여준다 (예: 60초 초과)
                    if let error = slot.wrappedValue.error {
                        Text(error).font(.caption).foregroundStyle(.red)
                    } else if slot.wrappedValue.isPreparing {
                        Text("영상 불러오는 중…").font(.caption).foregroundStyle(.secondary)
                    } else {
                        Text(slot.wrappedValue.data == nil ? "촬영 또는 앨범에서 선택" : "선택됨 · 탭해서 변경")
                            .font(.caption)
                            .foregroundStyle(slot.wrappedValue.data == nil ? .secondary : Color.brand)
                    }
                }
                Spacer()
                Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
            }
            .padding(12)
            .background(Color(.secondarySystemGroupedBackground))
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .confirmationDialog(title, isPresented: showOptions, titleVisibility: .visible) {
            Button("촬영하기") {
                if UIImagePickerController.isSourceTypeAvailable(.camera) {
                    showCamera.wrappedValue = true
                } else {
                    slot.wrappedValue.error = "이 기기에서는 카메라를 쓸 수 없어요. 앨범에서 선택해 주세요."
                }
            }
            Button("앨범에서 선택") { showPicker.wrappedValue = true }
            Button("취소", role: .cancel) {}
        }
        .photosPicker(isPresented: showPicker, selection: item, matching: .videos)
        .fullScreenCover(isPresented: showCamera) {
            CameraRecorderView { recorded in
                if let recorded {
                    Task { await loadVideo(slot: slot) { recorded } }
                }
            }
            .ignoresSafeArea()
        }
        .onChange(of: item.wrappedValue) { _, newValue in
            guard let newValue else { return }
            // 선택을 바로 비워 둬야 같은 영상을 다시 골라도 onChange 가 불린다
            item.wrappedValue = nil
            Task {
                await loadVideo(slot: slot) {
                    guard let movie = try await newValue.loadTransferable(type: MovieFile.self) else {
                        throw VideoError.unreadable
                    }
                    return movie.url
                }
            }
        }
    }

    // MARK: - 하단 분석 버튼

    private var analyzeBar: some View {
        Button { Task { await analyze() } } label: {
            Group {
                if isLoading || isPreparing {
                    HStack(spacing: 8) {
                        ProgressView().tint(.white)
                        Text(isLoading ? "분석 요청 진행 중…" : "영상 준비 중…")
                    }
                } else {
                    Text("분석하기")
                }
            }
            .font(.headline)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(canAnalyze && !isLoading && !isPreparing ? Color.brand : Color.gray.opacity(0.4))
            .foregroundStyle(.white)
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .disabled(!canAnalyze || isLoading || isPreparing)
        .accessibilityIdentifier("analysis.submit")
        .padding(.horizontal, 20)
        .padding(.vertical, 10)
        .background(.bar)
    }

    // MARK: - 분석 실행

    private func analyze() async {
        guard canAnalyze, !isLoading, !isPreparing else { return }
        let id = UUID()
        requestID = id
        let selectedExercise = exercise
        let sideData = currentViews.contains("side") ? side.data : nil
        let frontData = front.data
        isLoading = true
        startedAt = Date()
        uploadProgress = nil
        failure = nil
        defer { isLoading = false }
        do {
            let response = try await appState.run {
                try await $0.analyze(exercise: selectedExercise, sideVideo: sideData, frontVideo: frontData) { progress in
                    Task { @MainActor in
                        guard requestID == id, isLoading else { return }
                        uploadProgress = progress
                    }
                }
            }
            result = response
            showResults = true
            if response.sessionId != nil { appState.historyVersion += 1 }  // 기록 탭 새로고침
        } catch {
            failure = AnalysisFailure.describe(error)
        }
    }

    private func failureCard(_ failure: AnalysisFailure) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(failure.title, systemImage: "exclamationmark.triangle.fill")
                .font(.headline).foregroundStyle(.orange)
            Text(failure.message).font(.subheadline)
            Text("선택한 영상은 그대로 남아 있어요.")
                .font(.caption).foregroundStyle(.secondary)
            if failure.canRetry {
                Button("같은 영상으로 다시 시도") { Task { await analyze() } }
                    .buttonStyle(.borderedProminent)
                    .disabled(!canAnalyze || isPreparing || isLoading)
                    .accessibilityIdentifier("analysis.retry")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 16))
    }

    /// 고른/촬영한 영상 파일을 540p 로 압축해 카드에 담는다 (60초 초과면 카드에 오류 표시).
    /// 영상을 메모리에 통째로 올리지 않고 파일로 받아 길이부터 확인한다.
    private func loadVideo(slot: Binding<VideoSlot>, source: () async throws -> URL) async {
        failure = nil
        let loadID = UUID()
        slot.wrappedValue = VideoSlot(isPreparing: true, loadID: loadID)
        var result = VideoSlot(loadID: loadID)
        do {
            let url = try await source()
            defer { try? FileManager.default.removeItem(at: url) }
            result.data = try await VideoCompressor.prepare(url)
            result.thumb = await videoThumbnail(url)
        } catch {
            result.error = error.localizedDescription
        }
        // 처리 중에 다른 영상을 새로 골랐으면 이 (오래된) 결과는 버린다
        if slot.wrappedValue.loadID == loadID { slot.wrappedValue = result }
    }
}

/// 영상 카드 하나의 상태
struct VideoSlot {
    var data: Data?
    var thumb: UIImage?
    var isPreparing = false
    var error: String?
    var loadID = UUID()
}

/// 앨범 영상을 Data 대신 임시 파일로 받는다 (긴 영상도 메모리에 올리지 않음)
struct MovieFile: Transferable {
    let url: URL

    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .movie) { movie in
            SentTransferredFile(movie.url)
        } importing: { received in
            // 받은 파일은 이 블록이 끝나면 지워지므로 임시 폴더로 복사해 둔다
            let copy = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathExtension(received.file.pathExtension)
            try FileManager.default.copyItem(at: received.file, to: copy)
            return MovieFile(url: copy)
        }
    }
}

/// 영상 파일에서 대표 프레임(약 0.5초 지점) 썸네일을 뽑는다.
func videoThumbnail(_ url: URL) async -> UIImage? {
    let generator = AVAssetImageGenerator(asset: AVURLAsset(url: url))
    generator.appliesPreferredTrackTransform = true
    let time = CMTime(seconds: 0.5, preferredTimescale: 600)
    guard let result = try? await generator.image(at: time) else { return nil }
    return UIImage(cgImage: result.image)
}

#Preview {
    ContentView()
        .environment(AppState())
}
