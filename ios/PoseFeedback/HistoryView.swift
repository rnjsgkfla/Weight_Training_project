import SwiftUI

/// 기록 탭: 운동 캘린더(연속 기록) + 발전 추이 진입 + 기록 목록
struct HistoryView: View {
    @Environment(AppState.self) private var appState

    @State private var sessions: [SessionSummary] = []
    @State private var loaded = false
    @State private var errorMessage: String?
    /// nil = 전체 운동
    @State private var exerciseFilter: String?
    /// 캘린더에서 고른 날 (nil = 전체 기간)
    @State private var selectedDay: Date?
    @State private var month = Calendar.current.startOfMonth(for: .now)

    private let calendar = Calendar.current

    private var filtered: [SessionSummary] {
        sessions.filter { s in
            (exerciseFilter == nil || s.exercise == exerciseFilter)
            && (selectedDay == nil || calendar.isDate(s.createdAt, inSameDayAs: selectedDay!))
        }
    }

    /// 운동한 날 (현재 운동 필터 기준)
    private var workoutDays: Set<Date> {
        Set(sessions.filter { exerciseFilter == nil || $0.exercise == exerciseFilter }
            .map { calendar.startOfDay(for: $0.createdAt) })
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("운동", selection: $exerciseFilter) {
                        Text("전체").tag(String?.none)
                        ForEach(Exercises.all, id: \.key) { ex in
                            Text(ex.name).tag(String?.some(ex.key))
                        }
                    }
                }

                Section {
                    StreakHeader(days: workoutDays)
                    MonthCalendar(month: $month, workoutDays: workoutDays, selectedDay: $selectedDay)
                }

                Section("발전 추이") {
                    ForEach(Exercises.all.filter { exerciseFilter == nil || $0.key == exerciseFilter }, id: \.key) { ex in
                        NavigationLink { ProgressChartView(exercise: ex.key) } label: {
                            Label(ex.name, systemImage: "chart.line.uptrend.xyaxis")
                        }
                    }
                }

                Section {
                    if loaded && filtered.isEmpty {
                        Text(selectedDay == nil ? "아직 기록이 없어요. 분석 탭에서 운동 영상을 올려보세요."
                                                : "이 날은 기록이 없어요.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                    ForEach(filtered) { s in
                        NavigationLink { SessionDetailView(summary: s) } label: { SessionRow(session: s) }
                    }
                    .onDelete(perform: delete)
                } header: {
                    HStack {
                        Text(selectedDay.map { $0.formatted(.dateTime.month().day().weekday()) + " 기록" } ?? "기록")
                        Spacer()
                        if selectedDay != nil {
                            Button("전체 보기") { selectedDay = nil }.font(.caption)
                        }
                    }
                } footer: {
                    if let errorMessage { Text(errorMessage).foregroundStyle(.red) }
                }
            }
            .navigationTitle("기록")
            .overlay { if !loaded && errorMessage == nil { ProgressView() } }
            .refreshable { await load() }
            .task(id: appState.historyVersion) { await load() }
        }
    }

    private func load() async {
        do {
            sessions = try await appState.run { try await $0.sessions() }
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
        loaded = true
    }

    private func delete(at offsets: IndexSet) {
        let targets = offsets.map { filtered[$0] }
        Task {
            for s in targets {
                do {
                    try await appState.run { try await $0.deleteSession(id: s.id) }
                    sessions.removeAll { $0.id == s.id }
                } catch {
                    errorMessage = error.localizedDescription
                }
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
    let summary: SessionSummary
    @State private var response: AnalyzeResponse?
    @State private var errorMessage: String?

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
        .task {
            do { response = try await appState.run { try await $0.session(id: summary.id) } }
            catch { errorMessage = error.localizedDescription }
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
