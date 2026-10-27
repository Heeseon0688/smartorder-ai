# Docker · 클라우드 검증 기록

검증일: 2026-10-27, macOS arm64 (M2).

## 실행 환경

Colima 0.x (Apple Virtualization.framework, virtiofs) + Docker Engine 29.5.2 arm64, Docker Compose 5.6.1. 이미지: `python:3.12-slim-bookworm`, `node:22-bookworm-slim`, `postgres:17-bookworm` (모두 arm64 네이티브).

## 실행 완료

| 항목 | 결과 |
|---|---|
| `docker compose build` | 성공 (backend, frontend) |
| `docker compose up --wait` | db·backend·frontend 모두 **healthy** |
| PostgreSQL API 테스트 (`scripts/test-compose.sh`, 컨테이너 내부) | **36 passed** — 격리된 임시 스키마 |
| 백엔드 API 테스트 (SQLite, 네이티브) | **36 passed** |
| 명시적 `seed-demo` (Docker DB) | 매장 1, 메뉴 16, 주문 126, Alembic `0002` |
| Vite 프록시 경유 통합 흐름 (REST + WebSocket) | **10/10 통과** — 아래 참고 |
| `docker compose down` → `up` 후 데이터 유지 | 주문 127건 유지 (Volume 영속화) |
| Chrome Playwright E2E (`npm run test:e2e`) | **5 passed** (50.9s) |
| 프론트엔드 `npm run build` | 성공 (tsc + Vite) |

통합 흐름 (`http://localhost:5173`, 브라우저와 같은 경로):
1. Vite 컨테이너가 프론트엔드 제공 → 2. `/api` 프록시로 메뉴 조회 → 3. 관리자 로그인·WS 티켓 →
4. 관리자·고객 WebSocket이 `/ws` 프록시로 연결 → 5. 주문 생성(서버 가격 재계산) 및 관리자 실시간 `order.created` 수신 →
6. 같은 Idempotency-Key 재전송 시 동일 주문 반환 → 7. 접수 대기→조리 중→완료가 고객 WS로 전달, 역방향 전환 409 →
8. SQL 통계 → 9. API 키 없는 통계 기반 분석 → 10. QR PNG 생성.

## 아직 실행하지 않음

| 항목 | 이유 |
|---|---|
| Vercel / Render / Neon 배포 및 공개 URL 테스트 | 사용자 승인 및 계정 연결 전 |
| 실제 휴대폰 QR 스캔 | 배포 후 (로컬 QR은 localhost를 가리킴) |
| 실제 OpenAI API 호출 | API 키 미설정 |
| Excel(.xlsx) 다운로드 | 미구현 — 현재 기능은 CSV 내보내기 |

## 이번에 수정한 구성 문제

- **Render 프록시 뒤 로그인 제한**: TCP 피어가 Render 프록시라 모든 사용자가 같은 IP로 보여, 10회 실패 시 전 관리자 로그인이 5분간 차단될 수 있었음 → `FORWARDED_ALLOW_IPS=*` 추가, 위조 X-Forwarded-For 우회 대비 계정별(20회/5분) 제한 추가 + 테스트.
- **`/api/ready`가 `0002` 하드코딩**: 새 마이그레이션 추가 시 Render 헬스체크 실패 → Alembic head를 동적으로 비교.
- **Compose backend healthcheck**: Dockerfile 기본값(30초 간격)으로 frontend 시작이 최소 30초 지연 → Compose에서 5초 간격으로 재정의.
- **frontend 컨테이너가 시작할 때마다 `npm ci`**: 매번 전체 재설치·네트워크 필요 → `package-lock.json` 해시가 바뀐 경우에만 재설치 (`frontend/scripts/docker-dev.sh`).
