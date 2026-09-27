import SwiftUI
import Charts

/// 운동별 발전 추이: 점수 그래프 + 항목별(허용오차 대비) 그래프 + 요약
struct ProgressChartView: View {
    @Environment(AppState.self) private var appState
    let exercise: String

    @State private var points: [ProgressPoint] = []
    @State private var loaded = false
    @State private var errorMessage: String?
    @State private var featureId: String?

    /// 가장 최근 기록 기준의 항목 목록 (측면/정면 순)
    private var features: [FeatureProgress] { points.last?.features ?? [] }

    /// x축: 기록 순서 1…N (0부터 시작하지 않게 고정)
    private var xDomain: ClosedRange<Int> { 1...max(points.count, 2) }
    /// x축 눈금: 기록이 많아도 6개 안팎만 (1, 1+step, …)
    private var xTicks: [Int] {
        let n = max(points.count, 2)
        return Array(stride(from: 1, through: n, by: max(1, (n + 5) / 6)))
    }

    private var selectedFeature: FeatureProgress? {
        features.first { $0.id == featureId } ?? features.first
    }

    var body: some View {
        List {
            if let errorMessage {
                Text(errorMessage).foregroundStyle(.red)
            } else if loaded && points.isEmpty {
                ContentUnavailableView("아직 기록이 없어요", systemImage: "chart.line.uptrend.xyaxis",
                                       description: Text("\(Exercises.name(exercise)) 영상을 분석하면 여기에 쌓여요."))
            } else if !points.isEmpty {
                summarySection
                scoreSection
                featureSection
            }
        }
        .navigationTitle("\(Exercises.name(exercise)) 추이")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { if !loaded { ProgressView() } }
        .task { await load() }
    }

    // MARK: 요약

    private var summarySection: some View {
        Section {
            if points.count < 2 {
                Text("기록이 2회 이상 쌓이면 변화를 비교해 드려요.")
                    .font(.subheadline).foregroundStyle(.secondary)
            } else {
                if let first = points.first?.score, let last = points.last?.score {
                    let diff = last - first
                    summaryRow("점수", "\(first)점 → \(last)점 (\(diff >= 0 ? "+" : "")\(diff))",
                               icon: diff >= 0 ? "arrow.up.right.circle.fill" : "arrow.down.right.circle.fill",
                               tint: diff >= 0 ? .green : .red)
                }
                if let best = mostImproved {
                    summaryRow("가장 좋아진 항목", best.label, icon: "hand.thumbsup.fill", tint: .green)
                }
            }
            let persistent = features.filter { $0.faultRate >= 0.5 }.map(\.name)
            if !persistent.isEmpty {
                summaryRow("최근 계속 지적된 항목", persistent.joined(separator: ", "),
                           icon: "exclamationmark.triangle.fill", tint: .orange)
            }
        } header: {
            Text("\(points.count)회 기록")
        }
    }

    /// 첫 기록 대비 최근 기록에서 avg_ratio 가 가장 많이 줄어든 항목
    private var mostImproved: FeatureProgress? {
        guard let first = points.first, let last = points.last else { return nil }
        let before = Dictionary(first.features.map { ($0.id, $0.avgRatio) }, uniquingKeysWith: { a, _ in a })
        return last.features
            .compactMap { f in before[f.id].map { (f, $0 - f.avgRatio) } }
            .filter { $0.1 > 0.1 }
            .max { $0.1 < $1.1 }?.0
    }

    private func summaryRow(_ title: String, _ value: String, icon: String, tint: Color) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon).foregroundStyle(tint)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.caption).foregroundStyle(.secondary)
                Text(value).font(.subheadline)
            }
        }
    }

    // MARK: 점수 그래프

    private var scoreSection: some View {
        Section("점수") {
            Chart(Array(points.enumerated()), id: \.offset) { i, p in
                if let score = p.score {
                    LineMark(x: .value("기록", i + 1), y: .value("점수", score))
                        .foregroundStyle(Color.brand)
                    PointMark(x: .value("기록", i + 1), y: .value("점수", score))
                        .foregroundStyle(Color.brand)
                }
            }
            .chartYScale(domain: 0...100)
            .chartXScale(domain: xDomain, range: .plotDimension(padding: 16))
            .chartXAxis {
                AxisMarks(values: xTicks) {  // 라벨을 눈금 가운데 정렬 (왼쪽 정렬이면 마지막 라벨이 잘려 사라짐)
                    AxisGridLine(); AxisTick(); AxisValueLabel(anchor: .top)
                }
            }
            .chartYAxis { AxisMarks(position: .leading) }  // 오른쪽 끝 x 눈금과 겹치지 않게
            .chartXAxisLabel("기록 순서")
            .frame(height: 180)
            .padding(.vertical, 8)
        }
    }

    // MARK: 항목별 그래프

    private var featureSection: some View {
        Section {
            Picker("항목", selection: Binding(get: { selectedFeature?.id }, set: { featureId = $0 })) {
                ForEach(features, id: \.id) { f in
                    Text(f.label).tag(String?.some(f.id))
                }
            }
            if let f = selectedFeature {
                Chart {
                    ForEach(Array(points.enumerated()), id: \.offset) { i, p in
                        if let v = p.features.first(where: { $0.id == f.id }) {
                            LineMark(x: .value("기록", i + 1), y: .value("허용오차 대비", v.avgRatio))
                                .foregroundStyle(Color.orange)
                            PointMark(x: .value("기록", i + 1), y: .value("허용오차 대비", v.avgRatio))
                                .foregroundStyle(v.avgRatio > 1 ? Color.orange : Color.green)
                        }
                    }
                    RuleMark(y: .value("허용오차", 1))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
                        .foregroundStyle(.secondary)
                        .annotation(position: .top, alignment: .leading) {
                            Text("허용 범위").font(.caption2).foregroundStyle(.secondary)
                        }
                }
                .chartXScale(domain: xDomain, range: .plotDimension(padding: 16))
                .chartXAxis {
                AxisMarks(values: xTicks) {  // 라벨을 눈금 가운데 정렬 (왼쪽 정렬이면 마지막 라벨이 잘려 사라짐)
                    AxisGridLine(); AxisTick(); AxisValueLabel(anchor: .top)
                }
            }
                .chartYAxis { AxisMarks(position: .leading) }  // 오른쪽 끝 x 눈금과 겹치지 않게
                .chartXAxisLabel("기록 순서")
                .frame(height: 200)
                .padding(.vertical, 8)
            }
        } header: {
            Text("항목별 변화")
        } footer: {
            Text("모범 자세에서 벗어난 정도를 허용오차 기준으로 나타낸 값이에요. 점선(1) 아래면 허용 범위 안이고, 낮을수록 좋아요.")
        }
    }

    private func load() async {
        do {
            points = try await appState.run { try await $0.progress(exercise: exercise) }.points
        } catch {
            errorMessage = error.localizedDescription
        }
        loaded = true
    }
}
