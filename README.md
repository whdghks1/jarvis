# JARVIS v0.3

FastAPI, OpenAI Agents SDK, PostgreSQL로 만드는 개인 AI 비서입니다.
현재 범위는 단일 사용자 `owner`의 대화 세션, 프로필, 장기 기억과 모바일
채팅 화면과 Android 앱입니다. 공개 서비스나 다중 사용자 회원 시스템을 전제로
하지 않습니다.

## 주요 기능

- 대화와 메시지 영구 저장
- 이전 메시지를 포함한 연속 대화
- OpenAI 토큰 없는 직접 메모리 저장
- 안정적인 key를 이용한 메모리 갱신 및 중복 방지
- 사용자 프로필 관리
- 휴대폰 대응 웹 UI와 홈 화면 설치(PWA)
- Kotlin/Jetpack Compose Android 앱
- SSE 기반 실시간 답변 스트리밍
- 앱 재실행 후 최근 대화 복원
- Android TTS 한국어 음성 응답
- 일회용 등록 코드를 이용한 기기 인증
- Android Keystore 기반 인증 토큰 보관
- 전화·지도·캘린더 작업 승인 및 감사 로그
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
`PAIRING_CODE`는 길고 예측하기 어려운 값으로 변경합니다. 값을 생략하면 서버가
시작할 때 임시 등록 코드가 터미널에 표시됩니다.

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
- JARVIS 화면: http://127.0.0.1:8000
- Android APK 설치: http://127.0.0.1:8000/downloads/jarvis.apk
- 프로세스 상태: http://127.0.0.1:8000/health
- DB 준비 상태: http://127.0.0.1:8000/ready

## 토큰 없이 기억 저장

`POST /memories`는 Agent를 거치지 않고 PostgreSQL에 직접 저장합니다.

```json
{
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
GET    /memories
PATCH  /memories/{memory_id}
DELETE /memories/{memory_id}
```

## 연속 대화

첫 요청에는 `conversation_id`를 생략합니다.

```json
{
  "message": "내일 회의 준비를 도와줘."
}
```

응답의 `conversation_id`를 다음 요청에 전달합니다.

```json
{
  "conversation_id": 1,
  "message": "오후 3시 일정이야."
}
```

`POST /chat`은 자연어 해석과 답변 생성을 위해 OpenAI 토큰을 사용합니다.
최근 대화는 `CONVERSATION_HISTORY_LIMIT` 범위에서 다시 Agent에 전달됩니다.

Android 앱은 `POST /chat/stream`을 사용합니다. SSE의 `conversation`, `delta`,
`done`, `error` 이벤트를 순서대로 처리하며, DB에는 스트림이 정상 완료된 최종
답변만 저장됩니다.

대화 관리 API:

```text
POST /conversations
GET  /conversations
GET  /conversations/{conversation_id}/messages
```

## 사용자 프로필

프로필은 일반 장기 기억과 분리해서 관리합니다. 이 API도 OpenAI 토큰을
사용하지 않습니다.

```text
PUT /profile
GET /profile
```

```json
{
  "display_name": "종환",
  "timezone": "Asia/Seoul",
  "locale": "ko-KR",
  "preferred_language": "Korean"
}
```

API 요청에는 `user_id`를 보내지 않습니다. 서버가 `.env`의 `OWNER_ID`를
사용하며 기본값은 `owner`입니다. DB의 `user_id` 컬럼은 기존 데이터 호환과
내부 소유권 표시를 위해 유지합니다.

## 휴대폰에서 사용

FastAPI가 모바일 채팅 화면도 함께 제공합니다. 같은 Wi-Fi 안에서만 쓸 때는
서버를 다음처럼 실행합니다.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

휴대폰 브라우저에서 `http://서버의-내부-IP:8000`으로 접속합니다. Safari나
Chrome의 **홈 화면에 추가**를 선택하면 앱처럼 실행할 수 있습니다.
웹 화면의 **Android 앱 설치** 버튼을 누르면 현재 빌드된 APK를
바로 다운로드합니다. 첫 설치 시 Android에서 해당 브라우저의
`알 수 없는 앱 설치`를 허용해야 할 수 있습니다.

집 밖에서도 사용하려면 서버와 휴대폰에 Tailscale을 설치한 뒤 서버의
Tailscale 주소로 접속하는 방식을 권장합니다. 공유기 포트포워딩으로 8000번
포트를 인터넷에 직접 공개하지 마세요. 브라우저나 Android 앱을 처음 연결할
때 서버의 `PAIRING_CODE`를 한 번 입력해야 합니다.

## 기기 인증

`AUTH_REQUIRED=true`이면 `/health`, `/ready`, 정적 화면과 기기 등록을 제외한
API에 Bearer 토큰이 필요합니다. 등록된 토큰은 서버에 SHA-256 해시로만
저장됩니다.

```text
POST   /device-registration
GET    /devices
DELETE /devices/{device_id}
```

기기 연결을 해제하면 해당 토큰은 즉시 사용할 수 없습니다. OpenAI API key는
Android 앱이나 웹 UI로 전달되지 않습니다.

## 안전한 휴대폰 작업

Agent가 아래 작업을 제안할 수 있지만 바로 실행하지는 않습니다.

```text
calendar.create  캘린더 작성 화면 열기
navigation.open 지도 앱에서 목적지 열기
phone.dial       전화번호가 입력된 다이얼러 열기
```

모든 작업은 `pending_confirmation` 상태로 생성되며 Android 앱에서 사용자가
승인해야 실행됩니다.

```text
POST /actions
GET  /actions?status=pending_confirmation
POST /actions/{action_id}/approve
POST /actions/{action_id}/cancel
POST /actions/{action_id}/result
```

전화는 자동 발신하지 않고 `ACTION_DIAL`만 사용합니다. 캘린더도 직접 기록하지
않고 Android 캘린더 작성 화면을 열어 사용자가 마지막으로 확인합니다.

## Android 앱

Android Studio에서 `android` 폴더를 프로젝트로 엽니다. 개발 서버 주소의
기본값은 에뮬레이터용 `http://10.0.2.2:8000`입니다. 실제 휴대폰에서는 첫
화면에서 Tailscale HTTPS 주소 또는 같은 Wi-Fi의 서버 주소를 입력합니다.

터미널 빌드:

```bash
cd android
export ANDROID_HOME="$HOME/Library/Android/sdk"
./gradlew assembleDebug
```

생성되는 APK:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

빌드가 완료되면 FastAPI의 `/downloads/jarvis.apk`와 웹 화면의
설치 버튼이 이 파일을 제공합니다.

Android 앱의 현재 기능:

- 서버와 기기 등록
- Keystore에 암호화된 토큰 저장
- 텍스트 채팅과 대화 이어가기
- 답변이 생성되는 즉시 표시되는 스트리밍
- 앱을 다시 열었을 때 마지막 대화와 메시지 복원
- 버튼 기반 한국어 음성 입력
- 한국어 TTS 응답과 음성 켜기·끄기 설정
- 실행 대기 작업 승인·취소
- 캘린더·지도·다이얼러 Intent 실행
- 기기 연결 해제

개발 빌드만 HTTP 접속을 허용합니다. 배포용 빌드는 HTTPS만 허용합니다.

## 외부 VPS 배포 (권장)

도메인은 필수가 아닙니다. 개인용 JARVIS에는 Ubuntu VPS에서 Docker Compose로
API와 PostgreSQL을 실행하고, Tailscale Serve의 `https://이름.tailnet.ts.net`
주소로 휴대폰에서 접속하는 구성을 권장합니다. API의 8000번 포트는
`127.0.0.1`에만 연결되므로 인터넷에 직접 노출되지 않습니다.

### 1. 로컬에서 APK 준비

Android SDK가 설치된 개발 컴퓨터에서 실행합니다.

```bash
./scripts/prepare-release.sh
```

생성된 `releases/JARVIS.apk`는 개인 서명 키를 만들기 전까지 디버그 서명된
개인 설치용 APK입니다. Git에는 포함되지 않으므로 서버로 별도 전송해야 합니다.

```bash
scp releases/JARVIS.apk 서버사용자@서버주소:/opt/jarvis/releases/JARVIS.apk
```

### 2. VPS 환경 설정

VPS에 Docker Engine, Docker Compose 플러그인, Git을 설치하고 프로젝트를
`/opt/jarvis`에 준비합니다. 환경 파일은 저장소에 올리지 않습니다.

```bash
cd /opt/jarvis
cp .env.production.example .env.production
openssl rand -hex 32
```

생성한 서로 다른 난수로 `.env.production`의 `PAIRING_CODE`와
`POSTGRES_PASSWORD`를 교체하고 `OPENAI_API_KEY`도 입력합니다. DB URL에 바로
사용되므로 `POSTGRES_PASSWORD`는 `openssl rand -hex`처럼 영문과 숫자로만
만드는 것이 안전합니다. 파일 권한도 제한합니다.

```bash
chmod 600 .env.production
./scripts/deploy-production.sh
curl http://127.0.0.1:8000/ready
```

### 3. Tailscale HTTPS 연결

서버와 Android 휴대폰을 같은 Tailscale 계정에 연결합니다. 서버에서 HTTPS
기능을 활성화한 뒤 다음 명령을 실행합니다.

```bash
./scripts/configure-tailscale.sh
```

출력된 `https://...ts.net` 주소를 Android 앱의 **개인 기기 연결** 화면에
입력합니다. 이제 `10.0.2.2` 대신 이 주소가 저장됩니다. 휴대폰에서는 Tailscale
VPN이 켜져 있어야 합니다. 공유기나 클라우드 방화벽에서 8000번 포트를 열지
마세요. VPS의 SSH 포트는 가능하면 키 인증과 Tailscale SSH로 제한합니다.

### 운영 명령

```bash
# 상태와 로그
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml logs -f api

# 새 버전 반영
./scripts/deploy-production.sh

# PostgreSQL 백업 (14일보다 오래된 로컬 백업 자동 정리)
./scripts/backup-production.sh

# 복원: 현재 DB를 변경하므로 백업 파일을 확인한 뒤 실행
./scripts/restore-production.sh backups/jarvis-날짜.sql.gz --yes
```

`scripts/backup-production.sh`를 VPS의 cron 또는 systemd timer에서 매일 실행하고,
백업 파일은 VPS 밖의 암호화된 저장소에도 복사하는 것이 좋습니다. OpenAI 키,
등록 코드, DB 비밀번호는 APK나 Git 저장소에 넣지 않습니다.

사용자 지정 도메인이 필요해지면 나중에 Caddy나 Cloudflare Tunnel을 추가할 수
있지만, 단일 사용자·개인 기기 구성에서는 Tailscale 주소만으로 충분합니다.

## 테스트

```bash
python -m pytest -q
```

테스트는 SQLite 메모리 DB와 가짜 Agent 응답을 사용하므로 PostgreSQL이나
OpenAI API 호출 없이 실행됩니다.

## 다음 단계

- 대화가 길어질 때 자동 요약
- PostgreSQL trigram/pgvector 의미 검색
- 토큰 사용량과 호출 지연 관측
- Android 전체 대화 목록과 대화 선택
- Room 기반 로컬 오프라인 캐시
- 빠른 실행 위젯
- WorkManager 기반 예약 알림
- Google Calendar/Gmail 연동
- 빅스비 Capsule 수준의 시스템 진입점과 Android App Actions 검토
