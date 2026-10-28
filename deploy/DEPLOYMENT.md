# 배포 가이드

Vercel(Frontend) · Render(Backend, Docker) · Neon(PostgreSQL) 구성입니다.

```text
브라우저 ──HTTPS──▶ Vercel (React 정적 파일, /api/* → Render 전달)
        ──WSS────▶ Render (FastAPI) ──TLS──▶ Neon (PostgreSQL)
```

## 1. Neon

1. 프로젝트 생성 (Render와 같은 리전 권장, 예: AWS Singapore)
2. **Connect**에서 접속 주소 두 개를 복사합니다.
   - Connection pooling **켬** (`-pooler` 포함) → `DATABASE_URL`
   - Connection pooling **끔** → `MIGRATION_DATABASE_URL`

## 2. Render (Backend)

**New → Web Service**에서 GitHub 저장소를 연결합니다.

| 항목 | 값 |
|---|---|
| Language | Docker |
| Root Directory | (비움) |
| Dockerfile Path | `./backend/Dockerfile` |
| Docker Build Context Directory | `./backend` |
| Health Check Path | `/api/ready` |
| Auto-Deploy | After CI Checks Pass |

환경변수 (예시: [backend.env.example](backend.env.example))

```dotenv
APP_ENV=production
DATABASE_URL=<Neon pooled URL>
MIGRATION_DATABASE_URL=<Neon direct URL>
FRONTEND_URL=https://<프로젝트>.vercel.app
ALLOWED_ORIGINS=["https://<프로젝트>.vercel.app"]
COOKIE_SECURE=true
SEED_DEMO=false
ENABLE_DEMO_LINK=false
FORWARDED_ALLOW_IPS=*
OPENAI_API_KEY=          # 선택
```

- 컨테이너가 시작할 때 DB 마이그레이션을 실행합니다. 데모 데이터는 만들지 않습니다.
- `FRONTEND_URL`은 QR 코드가 가리키는 주소입니다. `ALLOWED_ORIGINS`와 같은 주소여야 서버가 시작됩니다.

## 3. Vercel (Frontend)

GitHub 저장소를 Import합니다.

| 항목 | 값 |
|---|---|
| Root Directory | `frontend` |
| 환경변수 `BACKEND_ORIGIN` | Render 서비스 주소 (예: `https://<서비스>.onrender.com`, 끝에 `/` 없음) |

빌드 설정은 `frontend/vercel.json`에 있습니다. Vercel이 발급한 도메인이 Render의 `FRONTEND_URL`과 다르면 Render 환경변수 두 개를 수정합니다.

## 4. 관리자 계정 생성

운영 DB에는 데모 계정이 없습니다. 로컬에서 실행합니다.

```bash
python3 scripts/bootstrap-cloud.py
```

Neon direct URL, 메뉴 추가 여부, 관리자 이메일, 비밀번호(16자 이상)를 차례로 입력합니다. 입력한 주소와 비밀번호는 화면에 표시되지 않습니다.

## 참고

- Render 무료 플랜은 15분간 요청이 없으면 중지되어 첫 요청이 50초 정도 걸릴 수 있습니다.
- WebSocket 연결 상태를 메모리에 저장하므로 Render 인스턴스는 1개로 운영합니다.
- 배포 확인: `https://<서비스>.onrender.com/api/ready`가 `{"status":"ready"}`를 반환해야 합니다.
