@echo off
chcp 65001 > nul
echo [당근 광고 기획 도우미] 시작 중...

REM .env 파일 확인
if not exist .env (
    echo .env 파일이 없습니다. .env.example 을 복사해서 키를 입력해주세요.
    copy .env.example .env
    echo .env 파일을 생성했습니다. API 키를 입력 후 다시 실행하세요.
    pause
    exit /b 1
)

REM 가상환경 확인 및 생성
if not exist venv (
    echo 가상환경 생성 중...
    python -m venv venv
)

REM 가상환경 활성화
call venv\Scripts\activate.bat

REM 패키지 설치
echo 패키지 설치 확인 중...
pip install -r requirements.txt --quiet

REM 앱 실행
echo 앱 실행 중...
python main.py

pause
