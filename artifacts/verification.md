# 초기 MVP 검증 기록

Docker·클라우드 환경 추가 이후의 최신 결과는 [deployment-verification.md](deployment-verification.md)를 참고하세요.

검증일: 2026-10-27 (Asia/Seoul), macOS arm64.

- Python 3.12.16 / Node.js 22.23.4 / Google Chrome + Playwright.
- API 테스트: `backend/.venv/bin/python -m pytest -q` — **23 passed (5.05s)**.
- 최종 전체 Chrome E2E: **5 passed (52.6s)**.
- 이후 HTTP LAN 호환 토큰 생성 및 `/demo` 경로 추가에 대한 관련 E2E: **2 passed (18.6s)**.
- 최종 `npm run build`: TypeScript 및 Vite 성공, 큰 단일 번들 경고 해소.
- 설치 시 npm audit: 알려진 취약점 0개.
- WebSocket 이벤트 수신 후 7초 이내 상태 반영을 검증 (15초 polling보다 짧은 제한).
- 고객·관리자 브라우저 컨텍스트 분리. 모바일 390×844, 데스크톱 1440×1050.
- 브라우저 런타임 오류 없음, 모바일 가로 넘침 없음, QR PNG 10개 로딩.
- 차트 SVG 경로 존재와 모든 고객 메뉴 이미지 로딩 확인.
- 브라우저 E2E는 매 실행 시 별도 임시 SQLite DB와 8001/5174 서버 사용.
- API pytest는 테스트별 새 스키마를 가진 별도 임시 SQLite DB 사용.
- 단일 개발 실행 스크립트의 시작·헬스체크·종료도 검증.

## 캡처

- `admin-dashboard.png`: SQL 통계·차트·인기 메뉴·최근 주문.
- `customer-mobile.png`: 모바일 메뉴 화면, 전체 이미지 로딩 후 캡처.
- `customer-desktop.png`: 데스크톱 메뉴 화면.
- `order-completed.png`: 고객 주문을 관리자가 완료한 실시간 상태.
- `ai-analysis.png`: 실제 SQL 데이터 기반 API 키 없는 분석.

## 실행하지 않은 범위

- 실제 OpenAI 유료 API 요청: 키 없음. Structured Outputs 성공/실패는 mock 검증.
- 실제 휴대폰 카메라 QR 스캔: QR PNG와 URL, 모바일 Chrome 화면은 검증.
- PostgreSQL, 다중 워커, 실제 PG, 운영 부하·복구 테스트.

pytest의 의존성 경고 1개: 설치된 Starlette가 httpx 기반 TestClient에 deprecation 경고를 출력합니다. 테스트 실패는 없으며 향후 테스트 클라이언트 의존성 업데이트 시 대응할 사항입니다.
