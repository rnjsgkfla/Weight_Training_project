import SwiftUI

/// 기록 탭: 운동별 인바디식 리포트(점수·항목별 분석·부위별 상태) + 운동 캘린더 + 기록 목록
struct HistoryView: View {
    @Environment(AppState.self) private var appState

    @State private var sessions: [SessionSummary] = []
    @State private var points: [ProgressPoint] = []
    @State private var loaded = false
    @State private var errorMessage: String?
    /// 리포트를 볼 운동 (처음엔 가장 최근에 한 운동)
    @State private var exercise: String?
    /// 캘린더에서 고른 날
    @State private var selectedDay: Date?
    @State private var month = Calendar.current.startOfMonth(for: .now)

    private let calendar = Calendar.current

    private var currentExercise: String { exercise ?? sessions.first?.exercise ?? Exercises.all[0].key }

    /// 운동한 날 (모든 운동)
    private var workoutDays: Set<Date> { Set(sessions.map { calendar.startOfDay(for: $0.createdAt) }) }

    private var daySessions: [SessionSummary] {
        guard let selectedDay else { return [] }
        return sessions.filter { calendar.isDate($0.createdAt, inSameDayAs: selectedDay) }
    }

    private var exerciseSessions: [SessionSummary] { sessions.filter { $0.exercise == currentExercise } }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    if let errorMessage {
                        Label(errorMessage, systemImage: "exclamationmark.circle.fill")
                            .font(.subheadline).foregroundStyle(.red)
                            .reportCard()
                    }
                    if loaded && sessions.isEmpty {
                        ContentUnavailableView("아직 기록이 없어요", systemImage: "figure.strengthtraining.traditional",
                                               description: Text("분석 탭에서 운동 영상을 올리면 여기에 리포트가 쌓여요."))
                            .padding(.top, 40)
                    } else if loaded {
                        exercisePicker
                        report
                        calendarCard
                        recordList
                    }
                }
                .padding(16)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("기록")
            .overlay { if !loaded && errorMessage == nil { ProgressView() } }
            .refreshable { await load() }
            .task(id: appState.historyVersion) { await load() }
            .task(id: currentExercise + "\(appState.historyVersion)") { await loadProgress() }
        }
    }

    // MARK: 운동 선택

    private var exercisePicker: some View {
        Picker("운동", selection: Binding(get: { currentExercise }, set: { exercise = $0 })) {
            ForEach(Exercises.all, id: \.key) { ex in Text(ex.name).tag(ex.key) }
        }
        .pickerStyle(.segmented)
    }

    // MARK: 리포트 (점수 · 항목별 분석 · 부위별 상태)

    @ViewBuilder
    private var report: some View {
        if let latest = points.last {
            ScoreCard(points: points)
            FeatureAnalysisCard(latest: latest, previous: points.count >= 2 ? points[points.count - 2] : nil)
            BodyStatusCard(features: latest.features)
            NavigationLink { ProgressChartView(exercise: currentExercise) } label: {
                HStack {
                    Label("항목별 추이 자세히 보기", systemImage: "chart.line.uptrend.xyaxis")
                    Spacer()
                    Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
                }
                .reportCard()
            }
            .buttonStyle(.plain)
        } else {
            Text("\(Exercises.name(currentExercise)) 기록이 아직 없어요. 분석 탭에서 영상을 올려보세요.")
                .font(.subheadline).foregroundStyle(.secondary)
                .reportCard()
        }
    }

    // MARK: 운동 캘린더 (날짜를 누르면 바로 아래에 그날 기록)

    private var calendarCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("운동 캘린더").font(.headline)
            StreakHeader(days: workoutDays)
            MonthCalendar(month: $month, workoutDays: workoutDays, selectedDay: $selectedDay)
            if let selectedDay {
                Divider()
                Text(selectedDay.formatted(.dateTime.month().day().weekday()) + " 기록")
                    .font(.subheadline.bold())
                ForEach(daySessions) { s in
                    NavigationLink { SessionDetailView(summary: s) } label: { SessionRow(session: s) }
                        .buttonStyle(.plain)
                }
            } else {
                Text("운동한 날을 누르면 그날 기록을 볼 수 있어요.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .reportCard()
    }

    // MARK: 기록 목록 (선택한 운동)

    private var recordList: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("\(Exercises.name(currentExercise)) 기록").font(.headline)
            if exerciseSessions.isEmpty {
                Text("아직 기록이 없어요.").font(.subheadline).foregroundStyle(.secondary)
            }
            ForEach(exerciseSessions) { s in
                NavigationLink { SessionDetailView(summary: s) } label: { SessionRow(session: s) }
                    .buttonStyle(.plain)
                    .contextMenu {
                        Button("기록 삭제", systemImage: "trash", role: .destructive) { delete(s) }
                    }
            }
            if !exerciseSessions.isEmpty {
                Text("기록을 누른 뒤 오른쪽 위 휴지통으로 삭제할 수 있어요.").font(.caption2).foregroundStyle(.secondary)
            }
        }
        .reportCard()
    }

    // MARK: 데이터

    private func load() async {
        do {
            sessions = try await appState.run { try await $0.sessions() }
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
        loaded = true
    }

    private func loadProgress() async {
        do {
            let ex = currentExercise
            points = try await appState.run { try await $0.progress(exercise: ex) }.points
        } catch {
            points = []
            errorMessage = error.localizedDescription
        }
    }

    private func delete(_ s: SessionSummary) {
        Task {
            do {
                try await appState.run { try await $0.deleteSession(id: s.id) }
                sessions.removeAll { $0.id == s.id }
                await loadProgress()
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}

// MARK: - 기록 한 줄

struct SessionRow: View {
    let session: SessionSummary

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: Exercises.icon(session.exercise))
                .font(.title3)
                .foregroundStyle(Color.brand)
                .frame(width: 32)
            VStack(alignment: .leading, spacing: 3) {
                Text(Exercises.name(session.exercise)).font(.body).bold()
                Text("\(session.createdAt.formatted(.dateTime.month().day().hour().minute())) · \(session.totalReps)회")
                    .font(.caption).foregroundStyle(.secondary)
                if !session.topFaults.isEmpty {
                    Text(session.topFaults.joined(separator: ", "))
                        .font(.caption).foregroundStyle(.orange)
                        .lineLimit(1)
                }
            }
            Spacer()
            if let score = session.score { ScoreBadge(score: score) }
        }
        .padding(.vertical, 2)
    }
}

struct ScoreBadge: View {
    let score: Int

    static func color(_ score: Int) -> Color {
        score >= 80 ? .green : score >= 50 ? .orange : .red
    }

    var body: some View {
        Text("\(score)점")
            .font(.subheadline).bold()
            .padding(.horizontal, 10).padding(.vertical, 4)
            .background(Self.color(score).opacity(0.15))
            .foregroundStyle(Self.color(score))
            .clipShape(Capsule())
    }
}

// MARK: - 기록 상세 (당시 분석 결과 그대로)

struct SessionDetailView: View {
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss
    let summary: SessionSummary
    @State private var response: AnalyzeResponse?
    @State private var errorMessage: String?
    @State private var confirmDelete = false

    var body: some View {
        Group {
            if let response {
                ResultsView(response: response,
                            title: summary.createdAt.formatted(.dateTime.month().day().hour().minute()))
            } else if let errorMessage {
                ContentUnavailableView("불러오지 못했어요", systemImage: "wifi.exclamationmark",
                                       description: Text(errorMessage))
            } else {
                ProgressView()
            }
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("삭제", systemImage: "trash") { confirmDelete = true }
                    .confirmationDialog("이 기록을 삭제할까요?", isPresented: $confirmDelete, titleVisibility: .visible) {
                        Button("기록 삭제", role: .destructive) { Task { await delete() } }
                        Button("취소", role: .cancel) {}
                    }
            }
        }
        .task {
            do { response = try await appState.run { try await $0.session(id: summary.id) } }
            catch { errorMessage = error.localizedDescription }
        }
    }

    private func delete() async {
        do {
            try await appState.run { try await $0.deleteSession(id: summary.id) }
            appState.historyVersion += 1  // 기록 탭 다시 불러오기
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - 연속 기록 / 이번 주 횟수

struct StreakHeader: View {
    let days: Set<Date>
    private let calendar = Calendar.current

    /// 오늘(또는 어제)부터 거꾸로 이어지는 연속 운동 일수
    private var streak: Int {
        var day = calendar.startOfDay(for: .now)
        if !days.contains(day) { day = calendar.date(byAdding: .day, value: -1, to: day)! }
        var count = 0
        while days.contains(day) {
            count += 1
            day = calendar.date(byAdding: .day, value: -1, to: day)!
        }
        return count
    }

    private var thisWeek: Int {
        guard let week = calendar.dateInterval(of: .weekOfYear, for: .now) else { return 0 }
        return days.filter { week.contains($0) }.count
    }

    var body: some View {
        HStack {
            stat("\(streak)일", "연속 운동", "flame.fill", .orange)
            Divider()
            stat("\(thisWeek)일", "이번 주", "calendar", .brand)
            Divider()
            stat("\(days.count)일", "전체", "checkmark.circle.fill", .green)
        }
        .padding(.vertical, 4)
    }

    private func stat(_ value: String, _ label: String, _ icon: String, _ tint: Color) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon).foregroundStyle(tint)
            Text(value).font(.headline)
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - 월간 캘린더

struct MonthCalendar: View {
    @Binding var month: Date
    let workoutDays: Set<Date>
    @Binding var selectedDay: Date?
    private let calendar = Calendar.current

    /// 주 단위 달력 칸 (7칸씩). 1일 앞·말일 뒤의 빈칸은 nil
    private var weeks: [[Date?]] {
        let range = calendar.range(of: .day, in: .month, for: month)!
        let leading = (calendar.component(.weekday, from: month) - calendar.firstWeekday + 7) % 7
        let days = range.map { calendar.date(byAdding: .day, value: $0 - 1, to: month)! }
        var cells: [Date?] = Array(repeating: nil, count: leading) + days
        cells += Array(repeating: nil, count: (7 - cells.count % 7) % 7)
        return stride(from: 0, to: cells.count, by: 7).map { Array(cells[$0..<$0 + 7]) }
    }

    var body: some View {
        VStack(spacing: 10) {
            HStack {
                Button { shift(-1) } label: { Image(systemName: "chevron.left") }
                Spacer()
                Text(month.formatted(.dateTime.year().month(.wide))).font(.headline)
                Spacer()
                Button { shift(1) } label: { Image(systemName: "chevron.right") }
            }
            .buttonStyle(.borderless)

            let symbols = calendar.veryShortWeekdaySymbols
            let ordered = Array(symbols[(calendar.firstWeekday - 1)...] + symbols[..<(calendar.firstWeekday - 1)])
            // List 행 안에서는 LazyVGrid 가 높이를 일정하게 못 돌려줘 레이아웃 무한루프(크래시)가
            // 나므로, 고정 높이의 HStack 줄로 그린다.
            VStack(spacing: 8) {
                HStack(spacing: 0) {
                    ForEach(Array(ordered.enumerated()), id: \.offset) { _, s in
                        Text(s).font(.caption2).foregroundStyle(.secondary).frame(maxWidth: .infinity)
                    }
                }
                ForEach(Array(weeks.enumerated()), id: \.offset) { _, week in
                    HStack(spacing: 0) {
                        ForEach(Array(week.enumerated()), id: \.offset) { _, day in
                            if let day { dayCell(day) } else { Color.clear.frame(maxWidth: .infinity, maxHeight: 34) }
                        }
                    }
                    .frame(height: 34)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private func dayCell(_ day: Date) -> some View {
        let didWork = workoutDays.contains(day)
        let isSelected = selectedDay.map { calendar.isDate($0, inSameDayAs: day) } ?? false
        let isToday = calendar.isDateInToday(day)
        return Button {
            selectedDay = isSelected ? nil : day
        } label: {
            Text("\(calendar.component(.day, from: day))")
                .font(.subheadline.weight(isToday ? .bold : .regular))
                .frame(maxWidth: .infinity, minHeight: 34, maxHeight: 34)
                .background(
                    Circle()
                        .fill(isSelected ? Color.brand : didWork ? Color.brand.opacity(0.18) : .clear)
                        .frame(width: 34, height: 34)
                )
                .foregroundStyle(isSelected ? .white : didWork ? Color.brand : .primary)
        }
        .buttonStyle(.borderless)
        .disabled(!didWork && !isSelected)
    }

    private func shift(_ months: Int) {
        month = calendar.date(byAdding: .month, value: months, to: month)!
    }
}

extension Calendar {
    func startOfMonth(for date: Date) -> Date {
        self.date(from: dateComponents([.year, .month], from: date))!
    }
}
