# JARVIS v0.2

FastAPI, OpenAI Agents SDK, PostgreSQL로 만드는 개인 AI 비서입니다.
현재 범위는 대화 세션, 사용자 프로필, 장기 기억입니다.

## 주요 기능

- 대화와 메시지 영구 저장
- 이전 메시지를 포함한 연속 대화
- OpenAI 토큰 없는 직접 메모리 저장
- 안정적인 key를 이용한 메모리 갱신 및 중복 방지
- 사용자 프로필 관리
- Alembic DB migration
- liveness/readiness 상태 확인

## 준비

- Python 3.11+
- Docker Desktop
- OpenAI API key

## 실행

환경 파일을 준비합니다.

```bash
cp .env.example .env
```

`.env`의 `OPENAI_API_KEY`를 실제 키로 변경합니다.

PostgreSQL을 실행합니다.

```bash
docker compose up -d
```

macOS/Linux에서 가상환경과 패키지를 설치합니다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

DB migration을 적용하고 API를 실행합니다.

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Windows PowerShell에서는 다음 명령을 사용합니다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

- API 문서: http://127.0.0.1:8000/docs
- 프로세스 상태: http://127.0.0.1:8000/health
- DB 준비 상태: http://127.0.0.1:8000/ready

## 토큰 없이 기억 저장

`POST /memories`는 Agent를 거치지 않고 PostgreSQL에 직접 저장합니다.

```json
{
  "user_id": "owner",
  "content": "사용자의 이름은 종환이다.",
  "type": "fact",
  "category": "profile",
  "importance": 0.9,
  "normalized_key": "profile.name"
}
```

동일한 사용자와 `normalized_key`로 다시 요청하면 새 행을 만들지 않고 기존
기억을 갱신합니다. `normalized_key`가 필요 없는 자유 형식 기억은 생략할 수
있습니다.

기억 조회와 삭제:

```text
GET    /memories/owner
PATCH  /memories/{memory_id}?user_id=owner
DELETE /memories/{memory_id}?user_id=owner
```

## 연속 대화

첫 요청에는 `conversation_id`를 생략합니다.

```json
{
  "user_id": "owner",
  "message": "내일 회의 준비를 도와줘."
}
```

응답의 `conversation_id`를 다음 요청에 전달합니다.

```json
{
  "user_id": "owner",
  "conversation_id": 1,
  "message": "오후 3시 일정이야."
}
```

`POST /chat`은 자연어 해석과 답변 생성을 위해 OpenAI 토큰을 사용합니다.
최근 대화는 `CONVERSATION_HISTORY_LIMIT` 범위에서 다시 Agent에 전달됩니다.

대화 관리 API:

```text
POST /conversations
GET  /conversations?user_id=owner
GET  /conversations/{conversation_id}/messages?user_id=owner
```

## 사용자 프로필

프로필은 일반 장기 기억과 분리해서 관리합니다. 이 API도 OpenAI 토큰을
사용하지 않습니다.

```text
PUT /profiles/owner
GET /profiles/owner
```

```json
{
  "display_name": "종환",
  "timezone": "Asia/Seoul",
  "locale": "ko-KR",
  "preferred_language": "Korean"
}
```

## 테스트

```bash
python -m pytest -q
```

테스트는 SQLite 메모리 DB와 가짜 Agent 응답을 사용하므로 PostgreSQL이나
OpenAI API 호출 없이 실행됩니다.

## 다음 단계

- 대화가 길어질 때 자동 요약
- PostgreSQL trigram/pgvector 의미 검색
- 실제 인증에서 `user_id` 주입
- 토큰 사용량과 호출 지연 관측
- 외부 작업 승인(HITL) 및 감사 로그
- Google Calendar/Gmail 연동
- Next.js UI와 스트리밍
- Voice와 능동 알림
