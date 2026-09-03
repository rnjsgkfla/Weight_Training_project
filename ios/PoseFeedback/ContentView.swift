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

    private let exercises = [("squat", "스쿼트"), ("lunge", "런지")]
    private let api = APIClient()

    var body: some View {
        NavigationStack {
            Form {
                Section("운동") {
                    Picker("운동 선택", selection: $exercise) {
                        ForEach(exercises, id: \.0) { Text($0.1).tag($0.0) }
                    }
                    .pickerStyle(.segmented)
                }

                Section {
                    videoRow("측면 영상", data: $sideData, thumb: $sideThumb, item: $sideItem,
                             showOptions: $showSideOptions, showPicker: $showSidePicker, showCamera: $showSideCamera)
                    videoRow("정면 영상", data: $frontData, thumb: $frontThumb, item: $frontItem,
                             showOptions: $showFrontOptions, showPicker: $showFrontPicker, showCamera: $showFrontCamera)
                } header: {
                    Text("영상 (하나 이상)")
                } footer: {
                    Text("촬영하거나 앨범에서 선택하세요. 전신이 화면에 다 나오게, 운동을 1회 이상 수행한 영상이어야 합니다.")
                }

                Section {
                    Button(action: { Task { await analyze() } }) {
                        if isLoading {
                            HStack(spacing: 8) {
                                ProgressView()
                                Text("영상 분석 중… (약 15~30초)")
                            }
                            .frame(maxWidth: .infinity)
                        } else {
                            Text("분석하기").frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(isLoading || (sideData == nil && frontData == nil))
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage).foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("운동 자세 피드백")
            .navigationDestination(isPresented: $showResults) {
                if let result { ResultsView(response: result) }
            }
        }
    }

    @ViewBuilder
    private func videoRow(_ title: String,
                          data: Binding<Data?>,
                          thumb: Binding<UIImage?>,
                          item: Binding<PhotosPickerItem?>,
                          showOptions: Binding<Bool>,
                          showPicker: Binding<Bool>,
                          showCamera: Binding<Bool>) -> some View {
        Button { showOptions.wrappedValue = true } label: {
            HStack {
                Text(title).foregroundStyle(.primary)
                Spacer()
                if let img = thumb.wrappedValue {
                    Image(uiImage: img)
                        .resizable()
                        .scaledToFill()
                        .frame(width: 56, height: 40)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                } else {
                    Image(systemName: "plus.circle").foregroundStyle(.tint)
                }
            }
            .contentShape(Rectangle())
        }
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
