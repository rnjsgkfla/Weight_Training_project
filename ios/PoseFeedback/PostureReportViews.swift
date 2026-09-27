import SwiftUI
import Charts

// 기록 탭의 인바디식 리포트 카드들: 종합 점수 · 항목별 분석(구간 막대) · 부위별 상태(인체 그림)

/// ratio(허용오차 대비 벗어난 정도)를 세 구간으로 나눈다. 인바디의 표준 이하/표준/표준 이상처럼.
enum PostureZone {
    case good, caution, fix

    init(ratio: Double) {
        self = ratio <= 1 ? .good : ratio <= 2 ? .caution : .fix
    }

    var label: String {
        switch self {
        case .good: "좋음"
        case .caution: "주의"
        case .fix: "교정 필요"
        }
    }

    var color: Color {
        switch self {
        case .good: .green
        case .caution: .orange
        case .fix: .red
        }
    }
}

extension View {
    /// 기록 탭 카드 공통 모양
    func reportCard() -> some View {
        padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.secondarySystemGroupedBackground))
            .clipShape(RoundedRectangle(cornerRadius: 18))
    }
}

// MARK: - 종합 점수

struct ScoreCard: View {
    let points: [ProgressPoint]

    private var latest: ProgressPoint? { points.last }
    private var previous: ProgressPoint? { points.count >= 2 ? points[points.count - 2] : nil }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("자세 점수").font(.headline)
                Spacer()
                if let latest {
                    Text(latest.createdAt.formatted(.dateTime.month().day()) + " 기록")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(latest?.score.map(String.init) ?? "-")
                    .font(.system(size: 48, weight: .bold, design: .rounded))
                    .foregroundStyle(latest?.score.map(ScoreBadge.color) ?? .secondary)
                Text("점").font(.title3).foregroundStyle(.secondary)
                Spacer()
                if let now = latest?.score, let before = previous?.score {
                    let diff = now - before
                    Label("\(diff >= 0 ? "+" : "")\(diff)점", systemImage: diff >= 0 ? "arrow.up" : "arrow.down")
                        .font(.subheadline.bold())
                        .foregroundStyle(diff >= 0 ? .green : .red)
                        .padding(.horizontal, 10).padding(.vertical, 5)
                        .background((diff >= 0 ? Color.green : Color.red).opacity(0.12))
                        .clipShape(Capsule())
                }
            }
            if points.count >= 2 {
                // 최근 10회 점수 미니 그래프
                let recent = Array(points.suffix(10).enumerated())
                Chart(recent, id: \.offset) { i, p in
                    if let s = p.score {
                        AreaMark(x: .value("기록", i), y: .value("점수", s))
                            .foregroundStyle(Color.brand.opacity(0.15))
                        LineMark(x: .value("기록", i), y: .value("점수", s))
                            .foregroundStyle(Color.brand)
                        PointMark(x: .value("기록", i), y: .value("점수", s))
                            .foregroundStyle(Color.brand).symbolSize(20)
                    }
                }
                .chartYScale(domain: 0...100)
                .chartXAxis(.hidden)
                .chartYAxis(.hidden)
                .frame(height: 56)
                Text("최근 \(recent.count)회 점수 변화").font(.caption2).foregroundStyle(.secondary)
            }
        }
        .reportCard()
    }
}

// MARK: - 항목별 분석 (구간 막대)

struct FeatureAnalysisCard: View {
    let latest: ProgressPoint
    let previous: ProgressPoint?

    /// 측면 → 정면 순으로 묶는다
    private var groups: [(view: String, features: [FeatureProgress])] {
        ["side", "front"].compactMap { v in
            let fs = latest.features.filter { $0.view == v }
            return fs.isEmpty ? nil : (v, fs)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("항목별 분석").font(.headline)
            zoneLegend
            ForEach(groups, id: \.view) { group in
                VStack(alignment: .leading, spacing: 10) {
                    Text(group.view == "side" ? "측면" : "정면")
                        .font(.caption.bold()).foregroundStyle(.secondary)
                    ForEach(group.features, id: \.id) { f in
                        featureRow(f, before: previous?.features.first { $0.id == f.id })
                    }
                }
            }
            Text("●이번 기록  ○지난 기록 · 모범 자세에서 벗어난 정도를 허용오차 기준으로 나타냈어요.")
                .font(.caption2).foregroundStyle(.secondary)
        }
        .reportCard()
    }

    private var zoneLegend: some View {
        HStack(spacing: 0) {
            Color.clear.frame(width: 96)
            ForEach([PostureZone.good, .caution, .fix], id: \.label) { z in
                Text(z.label).font(.caption2.bold()).foregroundStyle(z.color)
                    .frame(maxWidth: .infinity)
            }
            Color.clear.frame(width: 44)
        }
    }

    private func featureRow(_ f: FeatureProgress, before: FeatureProgress?) -> some View {
        HStack(spacing: 0) {
            Text(f.name).font(.subheadline).lineLimit(1).minimumScaleFactor(0.8)
                .frame(width: 96, alignment: .leading)
            ZoneBar(value: f.avgRatio, previous: before?.avgRatio)
            changeLabel(now: f.avgRatio, before: before?.avgRatio)
                .frame(width: 44, alignment: .trailing)
        }
    }

    @ViewBuilder
    private func changeLabel(now: Double, before: Double?) -> some View {
        if let before, abs(now - before) >= 0.1 {
            let better = now < before
            Text(better ? "개선" : "악화")
                .font(.caption2.bold())
                .foregroundStyle(better ? .green : .red)
        } else {
            Text("-").font(.caption2).foregroundStyle(.tertiary)
        }
    }
}

/// 좋음(0~1) · 주의(1~2) · 교정 필요(2~3+) 세 구간 막대 위에 내 위치를 점으로 찍는다
struct ZoneBar: View {
    let value: Double
    let previous: Double?
    private let maxValue = 3.0

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let x: (Double) -> CGFloat = { CGFloat(min(max($0, 0), maxValue) / maxValue) * w }
            ZStack(alignment: .leading) {
                HStack(spacing: 2) {
                    ForEach([PostureZone.good, .caution, .fix], id: \.label) { z in
                        RoundedRectangle(cornerRadius: 3).fill(z.color.opacity(0.18))
                    }
                }
                .frame(height: 8)
                if let previous {
                    Circle().stroke(Color.secondary, lineWidth: 1.5)
                        .frame(width: 12, height: 12)
                        .offset(x: x(previous) - 6)
                }
                Circle().fill(PostureZone(ratio: value).color)
                    .frame(width: 14, height: 14)
                    .overlay(Circle().stroke(.white, lineWidth: 2))
                    .offset(x: x(value) - 7)
            }
            .frame(height: geo.size.height)
        }
        .frame(height: 18)
    }
}

// MARK: - 부위별 상태 (앞에서 본 인체 그림)

struct BodyStatusCard: View {
    let features: [FeatureProgress]

    /// 인체 그림의 관절 위치 (0~1 정규 좌표, 앞에서 본 모습 → 사람의 왼쪽이 화면 오른쪽)
    private enum Joint: CaseIterable {
        case lShoulder, rShoulder, lElbow, rElbow, lWrist, rWrist, lHip, rHip, lKnee, rKnee, lAnkle, rAnkle

        var point: CGPoint {
            switch self {
            case .rShoulder: CGPoint(x: 0.36, y: 0.24)
            case .lShoulder: CGPoint(x: 0.64, y: 0.24)
            case .rElbow: CGPoint(x: 0.29, y: 0.40)
            case .lElbow: CGPoint(x: 0.71, y: 0.40)
            case .rWrist: CGPoint(x: 0.25, y: 0.55)
            case .lWrist: CGPoint(x: 0.75, y: 0.55)
            case .rHip: CGPoint(x: 0.43, y: 0.54)
            case .lHip: CGPoint(x: 0.57, y: 0.54)
            case .rKnee: CGPoint(x: 0.42, y: 0.74)
            case .lKnee: CGPoint(x: 0.58, y: 0.74)
            case .rAnkle: CGPoint(x: 0.41, y: 0.94)
            case .lAnkle: CGPoint(x: 0.59, y: 0.94)
            }
        }
    }

    /// 판정 항목 → 해당 부위 관절
    private static let featureJoints: [String: [Joint]] = [
        "knee": [.lKnee, .rKnee], "back_knee": [.lKnee, .rKnee], "valgus": [.lKnee, .rKnee],
        "knee_travel": [.lKnee, .rKnee], "sym_knee": [.lKnee, .rKnee],
        "hip": [.lHip, .rHip], "hip_depth": [.lHip, .rHip], "sym_hip": [.lHip, .rHip],
        "stance": [.lAnkle, .rAnkle],
        "arm_L": [.lShoulder], "arm_R": [.rShoulder], "shoulder_height_diff": [.lShoulder, .rShoulder],
        "elbow_L": [.lElbow], "elbow_R": [.rElbow],
        "wrist_L": [.lWrist], "wrist_R": [.rWrist],
    ]

    /// 관절별로 가장 나쁜 항목의 ratio (판정하지 않은 관절은 없음)
    private var jointRatio: [Joint: Double] {
        var out: [Joint: Double] = [:]
        for f in features {
            for j in Self.featureJoints[f.feature] ?? [] {
                out[j] = max(out[j] ?? 0, f.avgRatio)
            }
        }
        return out
    }

    /// 상체 기울기(trunk)는 몸통 선 색으로
    private var trunkZone: PostureZone? {
        features.filter { $0.feature == "trunk" }.map(\.avgRatio).max().map(PostureZone.init)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("부위별 상태").font(.headline)
            HStack(alignment: .center, spacing: 16) {
                figure.frame(width: 150, height: 230)
                VStack(alignment: .leading, spacing: 8) {
                    ForEach([PostureZone.good, .caution, .fix], id: \.label) { z in
                        Label { Text(z.label).font(.caption) } icon: {
                            Circle().fill(z.color).frame(width: 10, height: 10)
                        }
                    }
                    Label { Text("판정 안 함").font(.caption) } icon: {
                        Circle().fill(Color.gray.opacity(0.35)).frame(width: 10, height: 10)
                    }
                    Text("앞에서 본 모습이에요.\n(내 왼쪽 = 그림 오른쪽)")
                        .font(.caption2).foregroundStyle(.secondary)
                        .padding(.top, 4)
                }
            }
            .frame(maxWidth: .infinity)
        }
        .reportCard()
    }

    private var figure: some View {
        let ratios = jointRatio
        return Canvas { ctx, size in
            func p(_ j: Joint) -> CGPoint { CGPoint(x: j.point.x * size.width, y: j.point.y * size.height) }
            let bone = GraphicsContext.Shading.color(.gray.opacity(0.35))
            func line(_ a: CGPoint, _ b: CGPoint, _ shading: GraphicsContext.Shading = bone) {
                var path = Path(); path.move(to: a); path.addLine(to: b)
                ctx.stroke(path, with: shading, style: StrokeStyle(lineWidth: 6, lineCap: .round))
            }
            // 머리
            let head = CGRect(x: size.width * 0.5 - 14, y: size.height * 0.04, width: 28, height: 28)
            ctx.fill(Path(ellipseIn: head), with: bone)
            // 몸통 (상체 기울기 판정 색)
            let neck = CGPoint(x: size.width * 0.5, y: size.height * 0.2)
            let pelvis = CGPoint(x: size.width * 0.5, y: size.height * 0.54)
            line(neck, pelvis, trunkZone.map { .color($0.color.opacity(0.8)) } ?? bone)
            // 팔다리
            line(p(.lShoulder), p(.rShoulder))
            line(p(.lHip), p(.rHip))
            for (a, b, c) in [(Joint.lShoulder, Joint.lElbow, Joint.lWrist), (.rShoulder, .rElbow, .rWrist),
                              (.lHip, .lKnee, .lAnkle), (.rHip, .rKnee, .rAnkle)] {
                line(p(a), p(b)); line(p(b), p(c))
            }
            // 관절 점
            for j in Joint.allCases {
                let color = ratios[j].map { PostureZone(ratio: $0).color } ?? .gray.opacity(0.35)
                let r: CGFloat = ratios[j] == nil ? 5 : 8
                let c = p(j)
                ctx.fill(Path(ellipseIn: CGRect(x: c.x - r, y: c.y - r, width: r * 2, height: r * 2)), with: .color(color))
            }
        }
    }
}
