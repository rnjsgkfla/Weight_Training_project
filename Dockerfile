# 운동 자세 피드백 API 백엔드 (FastAPI + MediaPipe 파이프라인)
FROM python:3.11-slim

# OpenCV / MediaPipe 런타임에 필요한 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 설치 (소스보다 앞에 둬서 레이어 캐시 활용)
# mediapipe 등 큰 휠 다운로드가 느려 타임아웃 나는 경우가 있어 넉넉히 재시도한다.
COPY requirements-api.txt .
RUN pip install --no-cache-dir --timeout=180 --retries=6 -r requirements-api.txt

# 소스 + 원본 영상(data/raw) 복사
COPY . .

# 기준(모범) 데이터 생성: data/processed 는 .gitignore 라 이미지 빌드 시
# 원본 영상에서 재생성해 이미지 안에 굽는다 (스쿼트·런지, 사레레는 원본 없어 건너뜀).
RUN python build_references.py

# Cloud Run 은 PORT 환경변수를 주입한다 (기본 8080). 0.0.0.0 바인딩 필수.
ENV PORT=8080
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT}"]
