import SwiftUI

// MARK: - 결과 목록 (뷰별 그룹)

struct ResultsView: View {
    let response: AnalyzeResponse

    /// 측면/정면 등 뷰 순서를 유지하며 그룹화
    private var groups: [(view: String, items: [FeedbackItem])] {
        var order: [String] = []
        var map: [String: [FeedbackItem]] = [:]
        for it in response.items {
            let v = it.view ?? "결과"
            if map[v] == nil { order.append(v); map[v] = [] }
            map[v]?.append(it)
        }
        return order.map { ($0, map[$0] ?? []) }
    }

    var body: some View {
        Group {
            if response.items.isEmpty {
                ContentUnavailableView {
                    Label("결과 없음", systemImage: "exclamationmark.magnifyingglass")
                } description: {
                    Text(response.summary
                        .replacingOccurrences(of: "⚠️ ", with: ""))
                }
            } else {
                List {
                    ForEach(groups, id: \.view) { group in
                        Section {
                            ForEach(group.items) { item in
                                NavigationLink { ComparisonView(item: item) } label: {
                                    ItemRow(item: item)
                                }
                            }
                        } header: {
                            let faults = group.items.filter { !$0.ok }.count
                            let reps = Set(group.items.compactMap { $0.rep }).count
                            Text("\(group.view) · \(reps)회 · 지적 \(faults)건")
                        }
                    }
                }
            }
        }
        .navigationTitle("분석 결과")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - 목록 행

struct ItemRow: View {
    let item: FeedbackItem

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: item.ok ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .font(.title3)
                .foregroundStyle(item.ok ? Color.green : Color.orange)

            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.body)
                if let phase = item.phase, let t = item.timeSec {
                    Text("\(phase) 국면 · \(t, specifier: "%.1f")초")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer()
            if let dev = item.dev, let unit = item.unit {
                Text("\(dev >= 0 ? "+" : "")\(dev, specifier: "%.1f")\(unit)")
                    .font(.caption).bold()
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Color.orange.opacity(0.15))
                    .foregroundStyle(Color.orange)
                    .clipShape(Capsule())
            }
        }
        .padding(.vertical, 2)
    }

    private var title: String {
        let rep = item.rep ?? 0
        return item.ok ? "\(rep)회차 · 양호" : "\(rep)회차 · \(item.featureName ?? "")"
    }
}

// MARK: - 비교 화면

struct ComparisonView: View {
    let item: FeedbackItem

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // 모범 vs 내 자세 이미지
                HStack(alignment: .top, spacing: 10) {
                    imageCard("✅ 모범", uri: item.refImage)
                    imageCard("🙋 내 자세", uri: item.userImage)
                }

                if item.ok {
                    Label("기준과 큰 차이 없음 — 좋은 자세예요", systemImage: "checkmark.seal.fill")
                        .font(.headline)
                        .foregroundStyle(Color.green)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.green.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                } else {
                    valueComparison
                    if let msg = item.message {
                        HStack(alignment: .top, spacing: 8) {
                            Image(systemName: "arrow.right.circle.fill").foregroundStyle(Color.orange)
                            Text(msg)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                        .background(Color.orange.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }
            }
            .padding()
        }
        .navigationTitle(item.featureName ?? "비교")
        .navigationBarTitleDisplayMode(.inline)
    }

    private var valueComparison: some View {
        VStack(spacing: 12) {
            if let phase = item.phase, let t = item.timeSec {
                Text("\(phase) 국면 · \(t, specifier: "%.1f")초 지점")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            HStack(spacing: 12) {
                valueCard("모범", value: item.refVal, tint: .green)
                valueCard("내 자세", value: item.userVal, tint: .orange)
            }
            if let dev = item.dev, let unit = item.unit {
                Text("차이 \(dev >= 0 ? "+" : "")\(dev, specifier: "%.1f")\(unit)")
                    .font(.headline)
                    .foregroundStyle(Color.orange)
            }
        }
    }

    private func valueCard(_ title: String, value: Double?, tint: Color) -> some View {
        VStack(spacing: 4) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value != nil ? "\(value!, specifier: "%.1f")\(item.unit ?? "")" : "-")
                .font(.title2).bold()
                .foregroundStyle(tint)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .background(tint.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func imageCard(_ title: String, uri: String?) -> some View {
        VStack(spacing: 6) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            if let img = uiImage(from: uri) {
                Image(uiImage: img)
                    .resizable()
                    .scaledToFit()
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            } else {
                RoundedRectangle(cornerRadius: 10)
                    .fill(.secondary.opacity(0.15))
                    .frame(height: 220)
                    .overlay(Text("이미지 없음").font(.caption).foregroundStyle(.secondary))
            }
        }
        .frame(maxWidth: .infinity)
    }
}

/// "data:image/jpeg;base64,..." 문자열을 UIImage 로 디코딩한다.
func uiImage(from dataURI: String?) -> UIImage? {
    guard let s = dataURI,
          let comma = s.firstIndex(of: ","),
          let data = Data(base64Encoded: String(s[s.index(after: comma)...])) else {
        return nil
    }
    return UIImage(data: data)
}
