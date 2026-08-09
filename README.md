# JARVIS v0.1

첫 번째 목표는 **대화 + 장기 기억**입니다.

## 1. 준비

- Python 3.11+
- Docker Desktop
- OpenAI API key

## 2. 실행

```bash
cp .env.example .env
```

`.env` 파일의 `OPENAI_API_KEY`를 실제 키로 바꿉니다.

PostgreSQL 실행:

```bash
docker compose up -d
```

가상환경 및 패키지 설치:

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

브라우저:

- API 문서: http://127.0.0.1:8000/docs
- 상태 확인: http://127.0.0.1:8000/health

## 3. 첫 테스트

`POST /chat`

```json
{
  "user_id": "owner",
  "message": "내 이름은 종환이야. 기억해둬."
}
```

그리고 새 요청:

```json
{
  "user_id": "owner",
  "message": "내 이름이 뭐였지?"
}
```

메모리 확인:

`GET /memories/owner`

## v0.1 범위

- [x] JARVIS Agent
- [x] PostgreSQL
- [x] 장기 메모리 저장 도구
- [x] 장기 메모리 검색 도구
- [x] FastAPI
- [ ] 대화 세션 저장
- [ ] Next.js UI
- [ ] Google Calendar
- [ ] Gmail
- [ ] Web Search
- [ ] 승인(HITL)
- [ ] Voice

