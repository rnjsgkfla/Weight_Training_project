"""
schemas.py — API 요청/응답 스키마 (pydantic)

api.py(분석)·auth.py(로그인)·history.py(히스토리)가 함께 쓰므로 한곳에 모은다.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── 분석 결과 ──────────────────────────────────────────────────────────────────
class FeedbackItem(BaseModel):
    key: str            # 항목 식별자 (프론트에서 선택용, 항상 고유)
    label: str          # 목록에 표시할 이름
    detail: str         # 상세 설명 (markdown, 하위호환용)
    ok: bool            # 결함 없이 양호한 항목이면 True
    ref_image: str | None   # 모범 자세 프레임 (data:image/jpeg;base64,...)
    user_image: str | None  # 내 자세 프레임 (data:image/jpeg;base64,...)
    # 구조화 필드 (앱 비교 화면용, 양호 항목은 수치가 없어 null 일 수 있음)
    view: str | None = None          # 측면 / 정면
    rep: int | None = None           # 회차
    feature_name: str | None = None  # 결함 이름 (예: 무릎 깊이)
    phase: str | None = None         # 하강 / 최저 / 상승
    time_sec: float | None = None    # 결함 시각(초)
    ref_val: float | None = None     # 모범 값
    user_val: float | None = None    # 내 값
    dev: float | None = None         # 차이 (내 − 모범)
    unit: str | None = None          # 단위 (° 등)
    message: str | None = None       # 교정 문구


class RepMetric(BaseModel):
    feature: str        # 특징 식별자 (예: knee)
    name: str           # 한글 이름 (예: 무릎 깊이)
    unit: str           # 단위 (° 또는 빈 문자열)
    dev: float          # 가장 나빴던 순간의 편차 (내 − 모범, asym 은 절대값)
    tol: float          # 허용오차
    ratio: float        # 벗어난 정도 / 허용오차 (1 초과면 허용오차 밖, 0 이하면 기준보다 나쁜 적 없음)
    fault: bool         # 이 회차에서 결함으로 지적됐는지 (순간적 이탈은 ratio > 1 이어도 False)


class RepStats(BaseModel):
    view: str           # side / front
    rep: int            # 회차
    fault_count: int
    metrics: list[RepMetric]


class ScoreItem(BaseModel):
    item: str               # 점수 항목 식별자 (예: knee, pelvis)
    name: str               # 한글 이름 (예: 무릎 각도)
    weight: float           # 가중치 (운동별 합 1.00)
    unit: str = ''          # ° (각도) 또는 빈 문자열 (위치, 상체 길이=1 단위)
    tolerance: float        # 허용 오차 T (°, 또는 상체 길이=1 단위)
    mean_error: float       # DTW 대응쌍 평균 절대 오차 D
    normalized_error: float # e = min(D / T, 1)


class ScoreDetail(BaseModel):
    combined_error: float   # E = Σ weight × e
    items: list[ScoreItem]


class SessionStats(BaseModel):
    score: int | None           # 0~100 = 100 × (1 − E). 점수용 방향 영상이 없으면 null
    score_detail: ScoreDetail | None = None
    rep_count: dict[str, int]   # {view: 반복 수}
    reps: list[RepStats]
    warnings: list[str] = []    # 분석하지 못한 뷰의 안내 (사람 없음·전신 안 보임 등)


class IssueFrame(BaseModel):
    phase: str                  # 하강 / 최저 / 상승 (운동별 라벨)
    ref_image: str | None       # 모범 (data URI, 문제 관절 초록 표시)
    user_image: str | None      # 내 자세 (data URI, 문제 관절 빨강 표시)


class Issue(BaseModel):
    """문제별 카드: 같은 뷰·특징의 결함을 회차와 무관하게 묶은 것."""
    key: str                    # 예: side.knee
    view: str                   # side / front
    view_kr: str
    feature: str
    name: str                   # 항목 이름 (예: 무릎 깊이)
    unit: str                   # ° 또는 빈 문자열
    headline: str               # 문제 설명 (예: 오른쪽 팔꿈치를 기준보다 많이 굽혔습니다)
    advice: str | None          # 할 일 (예: 조금 더 펴보세요)
    reps: list[int]             # 이 문제가 나온 회차
    total_reps: int             # 그 뷰의 전체 회차 수
    severity: float             # 가장 심했던 순간의 벗어난 정도 / 허용오차
    rep: int                    # 가장 심했던 회차
    phase: str
    time_sec: float
    ref_val: float
    user_val: float
    thumb_ref: str | None       # 가장 심했던 순간 (data URI)
    thumb_user: str | None
    clip: list[IssueFrame]      # DTW 로 맞춘 비교 프레임 (상위 문제만, 없으면 빈 목록)


class AnalyzeResponse(BaseModel):
    exercise: str
    summary: str
    items: list[FeedbackItem]
    issues: list[Issue] | None = None   # 문제별 카드 (심각한 순). 이 기능 이전 기록은 null
    good_points: list[str] = []         # 모든 회차에서 지적되지 않은 항목
    stats: SessionStats         # 히스토리·발전 추이용 구조화 수치
    session_id: int | None = None   # 로그인 상태로 분석하면 저장된 기록 id


# ── 인증 ───────────────────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime


# ── 히스토리 ───────────────────────────────────────────────────────────────────
class SessionSummary(BaseModel):
    """히스토리 목록의 한 줄."""
    id: int
    exercise: str
    created_at: datetime
    score: int | None
    rep_count: dict[str, int]
    top_faults: list[str]       # 가장 자주 지적된 항목 이름 (최대 2개)


class SessionDetail(AnalyzeResponse):
    """히스토리 상세 = 당시 분석 응답 그대로 + 기록 시각."""
    session_id: int
    created_at: datetime


class FeatureProgress(BaseModel):
    view: str           # side / front
    feature: str
    name: str
    avg_ratio: float    # 이 기록의 회차 평균 ratio (낮을수록 좋음)
    fault_rate: float   # 이 기록에서 지적된 회차 비율 0~1


class ProgressPoint(BaseModel):
    session_id: int
    created_at: datetime
    score: int | None
    features: list[FeatureProgress]


class ProgressResponse(BaseModel):
    exercise: str
    points: list[ProgressPoint]     # 오래된 기록 → 최신 기록 순
