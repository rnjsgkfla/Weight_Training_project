import SwiftUI
import PhotosUI
import AVFoundation
import UIKit

struct ContentView: View {
    @State private var exercise = "squat"

    // 측면
    @State private var sideData: Data?
    @State private var sideThumb: UIImage?
    @State private var sideItem: PhotosPickerItem?
    @State private var showSideOptions = false
    @State private var showSidePicker = false
    @State private var showSideCamera = false
    // 정면
    @State private var frontData: Data?
    @State private var frontThumb: UIImage?
    @State private var frontItem: PhotosPickerItem?
    @State private var showFrontOptions = false
    @State private var showFrontPicker = false
    @State private var showFrontCamera = false

    @State private var isLoading = false
    @State private var result: AnalyzeResponse?
    @State private var showResults = false
    @State private var errorMessage: String?

    private let exercises = [("squat", "스쿼트", "figure.strengthtraining.traditional"),
                            ("lunge", "런지", "figure.strengthtraining.functional")]
    private let api = APIClient()

    private var canAnalyze: Bool { sideData != nil || frontData != nil }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 26) {
                    hero
                    exerciseSection
                    videoSection
                    if let errorMessage {
                        errorBanner(errorMessage)
                    }
                }
                .padding(20)
            }
            .background(Color(.systemGroupedBackground))
            .toolbar(.hidden, for: .navigationBar)
            .safeAreaInset(edge: .bottom) { analyzeBar }
            .navigationDestination(isPresented: $showResults) {
                if let result { ResultsView(response: result) }
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
            withAnimation(.easeInOut(duration: 0.15)) { exercise = key }
        } label: {
            VStack(spacing: 8) {
                Image(systemName: icon).font(.title2)
                Text(title).font(.subheadline).bold()
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
            .background(selected ? Color.brand.opacity(0.14) : Color(.secondarySystemGroupedBackground))
            .foregroundStyle(selected ? Color.brand : Color.primary)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(selected ? Color.brand : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - 영상 선택

    private var videoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("영상 (하나 이상)").font(.headline)
            videoCard("측면 영상", data: $sideData, thumb: $sideThumb, item: $sideItem,
                      showOptions: $showSideOptions, showPicker: $showSidePicker, showCamera: $showSideCamera)
            videoCard("정면 영상", data: $frontData, thumb: $frontThumb, item: $frontItem,
                      showOptions: $showFrontOptions, showPicker: $showFrontPicker, showCamera: $showFrontCamera)
            Text("촬영하거나 앨범에서 선택하세요. 전신이 화면에 다 나오게, 운동을 1회 이상 수행한 영상이어야 합니다.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func videoCard(_ title: String,
                           data: Binding<Data?>,
                           thumb: Binding<UIImage?>,
                           item: Binding<PhotosPickerItem?>,
                           showOptions: Binding<Bool>,
                           showPicker: Binding<Bool>,
                           showCamera: Binding<Bool>) -> some View {
        Button { showOptions.wrappedValue = true } label: {
            HStack(spacing: 14) {
                if let img = thumb.wrappedValue {
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
                    Text(thumb.wrappedValue == nil ? "촬영 또는 앨범에서 선택" : "선택됨 · 탭해서 변경")
                        .font(.caption)
                        .foregroundStyle(thumb.wrappedValue == nil ? .secondary : Color.brand)
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
                    errorMessage = "이 기기에서는 카메라를 쓸 수 없어요(시뮬레이터 등). 앨범에서 선택해 주세요."
                }
            }
            Button("앨범에서 선택") { showPicker.wrappedValue = true }
            Button("취소", role: .cancel) {}
        }
        .photosPicker(isPresented: showPicker, selection: item, matching: .videos)
        .fullScreenCover(isPresented: showCamera) {
            CameraRecorderView { recorded in
                if let recorded {
                    data.wrappedValue = recorded
                    Task { thumb.wrappedValue = await videoThumbnail(from: recorded) }
                }
            }
            .ignoresSafeArea()
        }
        .onChange(of: item.wrappedValue) { _, newValue in
            Task {
                let loaded = try? await newValue?.loadTransferable(type: Data.self)
                data.wrappedValue = loaded
                thumb.wrappedValue = loaded == nil ? nil : await videoThumbnail(from: loaded!)
            }
        }
    }

    // MARK: - 하단 분석 버튼

    private var analyzeBar: some View {
        Button { Task { await analyze() } } label: {
            Group {
                if isLoading {
                    HStack(spacing: 8) {
                        ProgressView().tint(.white)
                        Text("영상 분석 중… (약 15~30초)")
                    }
                } else {
                    Text("분석하기")
                }
            }
            .font(.headline)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(canAnalyze && !isLoading ? Color.brand : Color.gray.opacity(0.4))
            .foregroundStyle(.white)
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .disabled(!canAnalyze || isLoading)
        .padding(.horizontal, 20)
        .padding(.vertical, 10)
        .background(.bar)
    }

    private func errorBanner(_ message: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "exclamationmark.circle.fill").foregroundStyle(.red)
            Text(message).font(.subheadline)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.red.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 분석 실행

    private func analyze() async {
        isLoading = true
        errorMessage = nil
        do {
            result = try await api.analyze(exercise: exercise,
                                           sideVideo: sideData,
                                           frontVideo: frontData)
            showResults = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

/// 영상 데이터에서 대표 프레임(약 0.5초 지점) 썸네일을 뽑는다.
func videoThumbnail(from data: Data) async -> UIImage? {
    let tmp = FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString + ".mp4")
    guard (try? data.write(to: tmp)) != nil else { return nil }
    defer { try? FileManager.default.removeItem(at: tmp) }

    let asset = AVURLAsset(url: tmp)
    let generator = AVAssetImageGenerator(asset: asset)
    generator.appliesPreferredTrackTransform = true
    let time = CMTime(seconds: 0.5, preferredTimescale: 600)
    guard let result = try? await generator.image(at: time) else { return nil }
    return UIImage(cgImage: result.image)
}

#Preview {
    ContentView()
}
