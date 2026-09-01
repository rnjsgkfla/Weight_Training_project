import SwiftUI
import PhotosUI

struct ContentView: View {
    @State private var exercise = "squat"
    @State private var sideItem: PhotosPickerItem?
    @State private var frontItem: PhotosPickerItem?
    @State private var sideData: Data?
    @State private var frontData: Data?
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

                Section("영상 (하나 이상)") {
                    videoRow("측면 영상", item: $sideItem, data: $sideData)
                    videoRow("정면 영상", item: $frontItem, data: $frontData)
                }

                Section {
                    Button(action: { Task { await analyze() } }) {
                        if isLoading {
                            HStack { ProgressView(); Text("분석 중…") }
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
                          item: Binding<PhotosPickerItem?>,
                          data: Binding<Data?>) -> some View {
        PhotosPicker(selection: item, matching: .videos) {
            HStack {
                Text(title)
                Spacer()
                Image(systemName: data.wrappedValue == nil
                      ? "square.and.arrow.up" : "checkmark.circle.fill")
                    .foregroundStyle(data.wrappedValue == nil ? .secondary : .green)
            }
        }
        .onChange(of: item.wrappedValue) { _, newValue in
            Task {
                data.wrappedValue = try? await newValue?.loadTransferable(type: Data.self)
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

#Preview {
    ContentView()
}
