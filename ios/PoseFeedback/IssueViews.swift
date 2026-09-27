import SwiftUI

// MARK: - 문제 카드 (결과 목록의 한 줄)

struct IssueCard: View {
    let issue: Issue
    /// 가장 먼저 고칠 문제면 강조
    let isTop: Bool

    var body: some View {
        HStack(spacing: 12) {
            ZStack(alignment: .bottomTrailing) {
                if let img = uiImage(from: issue.thumbUser) {
                    Image(uiImage: img).resizable().scaledToFill()
                } else {
                    Color.secondary.opacity(0.15)
                }
                if !issue.clip.isEmpty {
                    Image(systemName: "play.circle.fill")
                        .font(.title3)
                        .foregroundStyle(.white, .black.opacity(0.45))
                        .padding(4)
                }
            }
            .frame(width: isTop ? 84 : 68, height: isTop ? 84 : 68)
            .clipShape(RoundedRectangle(cornerRadius: 10))

            VStack(alignment: .leading, spacing: 4) {
                Text(issue.headline)
                    .font(isTop ? .headline : .subheadline.weight(.semibold))
                    .lineLimit(2)
                Text("\(issue.viewKr) · \(issue.name)").font(.caption).foregroundStyle(.secondary).lineLimit(1)
                RepDots(reps: issue.reps, total: issue.totalReps)
            }
        }
        .padding(.vertical, 4)
    }

}

/// "5회 중 3회" + 회차별 점 (문제가 나온 회차는 빨강)
struct RepDots: View {
    let reps: [Int]
    let total: Int

    var body: some View {
        HStack(spacing: 4) {
            Text("\(total)회 중 \(reps.count)회").font(.caption2).foregroundStyle(.secondary)
            ForEach(1...max(total, 1), id: \.self) { k in
                Circle()
                    .fill(reps.contains(k) ? Color.red : Color.secondary.opacity(0.3))
                    .frame(width: 7, height: 7)
            }
        }
    }
}

// MARK: - 문제 상세: 모범 vs 내 자세 비교 재생

struct IssueDetailView: View {
    let issue: Issue

    @State private var frames: [(ref: UIImage?, user: UIImage?)] = []
    @State private var index = 0
    @State private var isPlaying = true
    @State private var isSlow = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(issue.headline).font(.title3.bold())

                if frames.isEmpty {
                    // 비교 재생이 없는 문제(하위 순위)는 가장 심했던 순간만 보여준다
                    comparison(ref: uiImage(from: issue.thumbRef), user: uiImage(from: issue.thumbUser))
                } else {
                    comparison(ref: frames[index].ref, user: frames[index].user)
                    player
                }

                if let advice = issue.advice {
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: "arrow.right.circle.fill").foregroundStyle(.orange)
                        Text(advice)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color.orange.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                VStack(alignment: .leading, spacing: 6) {
                    RepDots(reps: issue.reps, total: issue.totalReps)
                    Text("가장 심했던 순간: \(issue.rep)회차 · \(issue.phase) 국면 · \(issue.timeSec, specifier: "%.1f")초")
                        .font(.caption).foregroundStyle(.secondary)
                    if issue.unit == "°" {  // 위치 값(상체 길이 단위)은 숫자가 의미 없어 각도만 보여준다
                        Text("\(issue.name): 모범 \(Int(issue.refVal.rounded()))° · 내 자세 \(Int(issue.userVal.rounded()))°")
                            .font(.caption).foregroundStyle(.secondary)
                        Text("화면에 보이는 각도라 카메라 방향에 따라 실제보다 크게 나올 수 있어요.")
                            .font(.caption2).foregroundStyle(.tertiary)
                    }
                }
            }
            .padding()
        }
        .navigationTitle(issue.name)
        .navigationBarTitleDisplayMode(.inline)
        .task { decodeFrames() }
        .task(id: isPlaying) { await play() }
    }

    private func comparison(ref: UIImage?, user: UIImage?) -> some View {
        HStack(alignment: .top, spacing: 8) {
            frameCard("모범", image: ref, tint: .green)
            frameCard("내 자세 · \(issue.rep)회차", image: user, tint: .red)
        }
    }

    private func frameCard(_ title: String, image: UIImage?, tint: Color) -> some View {
        VStack(spacing: 4) {
            Text(title).font(.caption.bold()).foregroundStyle(tint)
            Group {
                if let image {
                    Image(uiImage: image).resizable().scaledToFit()
                } else {
                    Color.secondary.opacity(0.15).frame(height: 180)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(tint.opacity(0.6), lineWidth: 1.5))
        }
        .frame(maxWidth: .infinity)
    }

    /// 재생/정지 · 구간 슬라이더 · 0.5배속 · 현재 국면
    private var player: some View {
        VStack(spacing: 6) {
            HStack(spacing: 12) {
                Button { isPlaying.toggle() } label: {
                    Image(systemName: isPlaying ? "pause.fill" : "play.fill").frame(width: 24)
                }
                Slider(value: Binding(get: { Double(index) },
                                      set: { index = Int($0.rounded()); isPlaying = false }),
                       in: 0...Double(max(frames.count - 1, 1)), step: 1)
                Button(isSlow ? "0.5x" : "1x") { isSlow.toggle() }
                    .font(.caption.monospacedDigit())
                    .buttonStyle(.bordered)
            }
            Text(issue.clip[index].phase)
                .font(.caption.bold())
                .foregroundStyle(.secondary)
        }
    }

    private func decodeFrames() {
        guard frames.isEmpty else { return }
        frames = issue.clip.map { (uiImage(from: $0.refImage), uiImage(from: $0.userImage)) }
    }

    /// 재생 중이면 프레임을 반복해서 넘긴다 (초당 약 8장, 0.5배속이면 4장)
    private func play() async {
        while isPlaying && !Task.isCancelled {
            try? await Task.sleep(for: .milliseconds(isSlow ? 250 : 125))
            guard isPlaying, !frames.isEmpty else { return }
            index = (index + 1) % frames.count
        }
    }
}
