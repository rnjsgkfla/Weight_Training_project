import SwiftUI

struct ResultsView: View {
    let response: AnalyzeResponse

    var body: some View {
        List {
            Section {
                Text(response.summary)
                    .font(.subheadline)
            }
            if !response.items.isEmpty {
                Section("피드백 항목 (탭해서 비교)") {
                    ForEach(response.items) { item in
                        NavigationLink {
                            ItemDetailView(item: item)
                        } label: {
                            Text(item.label)
                        }
                    }
                }
            }
        }
        .navigationTitle("분석 결과")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct ItemDetailView: View {
    let item: FeedbackItem

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .top, spacing: 10) {
                    imageColumn("✅ 모범", uri: item.refImage)
                    imageColumn("🙋 내 자세", uri: item.userImage)
                }
                Text(item.detail)
                    .font(.body)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding()
        }
        .navigationTitle(item.label)
        .navigationBarTitleDisplayMode(.inline)
    }

    @ViewBuilder
    private func imageColumn(_ title: String, uri: String?) -> some View {
        VStack(spacing: 6) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            if let img = uiImage(from: uri) {
                Image(uiImage: img)
                    .resizable()
                    .scaledToFit()
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                RoundedRectangle(cornerRadius: 8)
                    .fill(.secondary.opacity(0.15))
                    .frame(height: 200)
                    .overlay(Text("이미지 없음").font(.caption).foregroundStyle(.secondary))
            }
        }
        .frame(maxWidth: .infinity)
    }
}

/// "data:image/jpeg;base64,..." 형식 문자열을 UIImage 로 디코딩한다.
func uiImage(from dataURI: String?) -> UIImage? {
    guard let s = dataURI,
          let comma = s.firstIndex(of: ","),
          let data = Data(base64Encoded: String(s[s.index(after: comma)...])) else {
        return nil
    }
    return UIImage(data: data)
}
