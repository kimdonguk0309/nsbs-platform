# NSBS P2P 네트워크 공유 플랫폼

## 구성
- backend/: FastAPI API 서버 (WireGuard 키 및 VPN 설정 자동화 포함)
- frontend/: Streamlit 기반 사용자 UI
- scripts/start.sh: 백엔드와 프론트엔드를 한번에 실행하는 스크립트

## 설치 및 실행

1. Python 설치 (3.10 이상 권장)

2. 의존성 설치
```bash
pip install -r requirements.txt
WireGuard 설치 및 설정 (OS별 패키지 설치 필요)

DB 초기화 및 서버 실행

bash
복사
편집
bash scripts/start.sh
브라우저에서 http://localhost:8501 접속 후 플랫폼 이용

주의
WireGuard 인터페이스 및 키 생성 권한 필요

서버는 8000 포트, 프론트엔드는 8501 포트를 사용합니다.

yaml
복사
편집

---

# 추가 안내

- DB(`payments.db`)는 처음 백엔드가 실행될 때 자동 생성됩니다.
- `wg-quick` 명령어는 Linux 환경에서 WireGuard 설정에 필요하므로, Windows는 별도 환경 필요.
- `streamlit_javascript` 패키지는 브라우저에서 위치 정보 권한 요청을 위한 라이브러리입니다.
- 실제 서비스 운영 시 HTTPS 적용과 보안 강화 필요.

---

필요하면 로컬에서 이 구조로 만든 뒤 아래 커맨드로 git 초기화, 커밋 후 푸시하면 깃허브에 올라갑니다.

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <원격 저장소 URL>
git push -u origin main
