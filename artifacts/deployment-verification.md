# Docker · 클라우드 검증 기록

검증일: 2026-10-27, macOS arm64 (M2).

## 실행 완료

| 항목 | 결과 |
|---|---|
| 백엔드 API 테스트 (SQLite, 네이티브) | **36 passed** — WebSocket 티켓, 마이그레이션, 운영 설정 가드 포함 |
| 프론트엔드 `npm run build` | 성공 (tsc + Vite) |

## 아직 실행하지 않음

| 항목 | 이유 |
|---|---|
| `docker compose build` / `up` | 이 Mac에 Docker가 설치되어 있지 않음 (`docker: command not found`) |
| PostgreSQL API 테스트 (`scripts/test-compose.sh`) | Docker 필요 |
| 컨테이너 간 통신·WebSocket 프록시 검증 | Docker 필요 |
| Vercel / Render / Neon 배포 | 사용자 승인 및 계정 연결 전 |

## 이번에 수정한 구성 문제

- **Render 프록시 뒤 로그인 제한**: TCP 피어가 Render 프록시라 모든 사용자가 같은 IP로 보여, 10회 실패 시 전 관리자 로그인이 5분간 차단될 수 있었음 → `FORWARDED_ALLOW_IPS=*` 추가, 위조 X-Forwarded-For 우회 대비 계정별(20회/5분) 제한 추가 + 테스트.
- **`/api/ready`가 `0002` 하드코딩**: 새 마이그레이션 추가 시 Render 헬스체크 실패 → Alembic head를 동적으로 비교.
- **Compose backend healthcheck**: Dockerfile 기본값(30초 간격)으로 frontend 시작이 최소 30초 지연 → Compose에서 5초 간격으로 재정의.
- **frontend 컨테이너가 시작할 때마다 `npm ci`**: 매번 전체 재설치·네트워크 필요 → `package-lock.json` 해시가 바뀐 경우에만 재설치 (`frontend/scripts/docker-dev.sh`).
