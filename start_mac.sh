#!/bin/bash
set -e

echo "[당근 광고 기획 도우미] 시작 중..."

# .env 파일 확인
if [ ! -f .env ]; then
    echo ".env 파일이 없습니다. .env.example 을 복사합니다."
    cp .env.example .env
    echo ".env 파일을 열어 API 키를 입력 후 다시 실행하세요."
    open .env 2>/dev/null || nano .env
    exit 1
fi

# 가상환경 확인 및 생성
if [ ! -d "venv" ]; then
    echo "가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화
source venv/bin/activate

# 패키지 설치
echo "패키지 설치 확인 중..."
pip install -r requirements.txt --quiet

# 앱 실행
echo "앱 실행 중..."
python main.py
