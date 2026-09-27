import SwiftUI

// MARK: - 결과 화면

/// 분석 결과. 문제 카드(issues)가 있으면 문제별 카드로, 없으면(이전 기록) 회차별 목록으로 보여준다.
struct ResultsView: View {
    let response: AnalyzeResponse
    var title = "분석 결과"

    var body: some View {
        Group {
            if response.items.isEmpty {
                ContentUnavailableView {
                    Label("결과 없음", systemImage: "exclamationmark.magnifyingglass")
                } description: {
                    Text(response.summary
                        .replacingOccurrences(of: "⚠️ ", with: ""))
                }
            } else if let issues = response.issues {
                List {
                    ScoreSections(response: response)
                    if issues.isEmpty {
                        Section {
                            Label("모든 회차에서 큰 문제가 없어요", systemImage: "checkmark.seal.fill")
                                .foregroundStyle(.green)
                        }
                    } else {
                        Section("이것부터 고쳐보세요") {
                            NavigationLink { IssueDetailView(issue: issues[0]) } label: {
                                IssueCard(issue: issues[0], isTop: true)
                            }
                        }
                        if issues.count > 1 {
                            Section("다른 고칠 점") {
                                ForEach(issues.dropFirst()) { issue in
                                    NavigationLink { IssueDetailView(issue: issue) } label: {
                                        IssueCard(issue: issue, isTop: false)
                                    }
                                }
                            }
                        }
                    }
                    if let good = response.goodPoints, !good.isEmpty {
                        Section("잘한 점") {
                            Label(good.joined(separator: ", "), systemImage: "hand.thumbsup.fill")
                                .font(.subheadline)
                                .foregroundStyle(.green)
                        }
                    }
                    Section {
                        NavigationLink {
                            List { RepGroupSections(items: response.items) }
                                .navigationTitle("회차별 결과")
                                .navigationBarTitleDisplayMode(.inline)
                        } label: {
                            Label("회차별 전체 결과 보기", systemImage: "list.bullet")
                        }
                    }
                }
            } else {
                List {
                    ScoreSections(response: response)
                    RepGroupSections(items: response.items)
                }
            }
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// 경고(분석하지 못한 뷰 등) + 자세 점수·계산 내역
struct ScoreSections: View {
    let response: AnalyzeResponse

    var body: some View {
        if let warnings = response.stats?.warnings, !warnings.isEmpty {
            Section {
                ForEach(warnings, id: \.self) { w in
                    Label(w, systemImage: "exclamationmark.triangle.fill")
                        .font(.subheadline)
                        .foregroundStyle(.orange)
                }
            }
        }
        if let score = response.stats?.score {
            Section {
                HStack {
                    Text("자세 점수").font(.headline)
                    Spacer()
                    ScoreBadge(score: score)
                }
                if let detail = response.stats?.scoreDetail {
                    // 계산 내역은 접어 둬서 문제 카드가 먼저 보이게 한다
                    DisclosureGroup("점수 계산 내역") {
                        ForEach(detail.items, id: \.item) { ScoreItemRow(item: $0) }
                        Text("모범 동작과 같은 순간끼리 비교한 평균 오차를 항목별 허용 오차로 나눠 가중 합산했어요. 막대가 짧을수록 모범에 가까워요.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    .font(.subheadline)
                }
            }
        }
    }
}

/// 회차별 결함 목록 (측면/정면 순서 유지)
struct RepGroupSections: View {
    let items: [FeedbackItem]

    private var groups: [(view: String, items: [FeedbackItem])] {
        var order: [String] = []
        var map: [String: [FeedbackItem]] = [:]
        for it in items {
            let v = it.view ?? "결과"
            if map[v] == nil { order.append(v); map[v] = [] }
            map[v]?.append(it)
        }
        return order.map { ($0, map[$0] ?? []) }
    }

    var body: some View {
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

// MARK: - 점수 항목 행 (평균 오차 / 허용 오차 막대)

struct ScoreItemRow: View {
    let item: ScoreItem

    private var unit: String { item.unit ?? "" }
    private var format: String { unit.isEmpty ? "%.2f" : "%.1f" }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(item.name).font(.subheadline)
                Text("\(Int((item.weight * 100).rounded()))%")
                    .font(.caption2).foregroundStyle(.secondary)
                Spacer()
                Text("평균 오차 \(String(format: format, item.meanError))\(unit) / 허용 \(String(format: format, item.tolerance))\(unit)")
                    .font(.caption).foregroundStyle(.secondary)
            }
            ProgressView(value: item.normalizedError)
                .tint(item.normalizedError < 0.34 ? .green : item.normalizedError < 0.67 ? .orange : .red)
        }
        .padding(.vertical, 2)
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
