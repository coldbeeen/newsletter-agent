# newsletter-agent

네이버 메일함에 쌓이는 기술 뉴스레터를 매일 하나의 데일리 리포트로 요약해 Slack으로 전달하는 에이전트.
자세한 요구사항은 [`newsletter-digest-agent-spec.md`](./newsletter-digest-agent-spec.md) 참고.

## 설치

Python 3.11 이상이 필요하다.

```bash
pip install -e ".[dev]"
```

## 환경변수

`.env.example`을 복사해 `.env`로 만들고 값을 채운다 (`.env`는 `.gitignore` 처리되어 있음).

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `NAVER_IMAP_USER` | ✅ | 네이버 메일 계정 (예: `myid@naver.com`) |
| `NAVER_IMAP_APP_PASSWORD` | ✅ | 네이버 애플리케이션 비밀번호 (2단계 인증 사용 시 발급 필요) |
| `NAVER_IMAP_HOST` | - | 기본값 `imap.naver.com` |
| `NAVER_IMAP_PORT` | - | 기본값 `993` |
| `ANTHROPIC_API_KEY` | ✅ | Anthropic API 키 |
| `CLAUDE_MODEL` | - | 기본값 `claude-haiku-4-5` (비용 효율 우선, 품질 부족 시 Sonnet 계열로 전환 검토) |
| `SLACK_WEBHOOK_URL` | Slack 전달 시 ✅ | Slack Incoming Webhook URL |
| `SEEN_URLS_RETENTION_DAYS` | - | 기본값 `30` (일). `state/seen_urls.json` 항목 보존 기간 |

네이버 메일 IMAP/SMTP 사용 활성화 및 애플리케이션 비밀번호 발급 방법은 네이버 메일 설정 > POP3/IMAP 설정 메뉴의
공식 안내를 참고한다.

## 로컬 실행 (드라이런)

Slack 없이 콘솔에 출력만 하려면:

```bash
newsletter-agent --console
```

또는 모듈로 직접 실행:

```bash
python -m newsletter_agent.pipeline --console
```

`--console`을 생략하면 `SLACK_WEBHOOK_URL`로 실제 전송한다 (미설정 시 콘솔로 폴백하며 에러 로그를 남긴다).

## 화이트리스트 편집

`whitelist.yaml`에서 발신 이메일 주소와 (동일 주소를 여러 뉴스레터가 공유하는 경우) `From` 표시 이름 목록을
관리한다. 코드 수정 없이 이 파일만 편집해 뉴스레터를 추가/삭제할 수 있다.

> **주의**: 화이트리스트 변경, Slack 등 전달 채널 변경은 스펙상 "반드시 사람 확인이 필요한" 항목이다.
> 에이전트가 이 파일이나 전달 방식을 스스로 수정하는 코드 경로는 존재하지 않으며, 항상 사람이 직접
> PR/커밋으로 반영해야 한다.

## 상태 파일

`state/seen_urls.json`은 중복 제거를 위해 최근 처리한 기사 URL과 처리 일자를 기록한다. GitHub Actions
스케줄 실행이 끝날 때마다 변경 사항이 자동으로 커밋된다. 로컬 실행 시에도 갱신되지만 커밋은 되지 않는다
(직접 `git add`/`git commit` 필요).

## GitHub Actions 스케줄 등록

1. 저장소를 **Private**으로 생성한다.
2. 저장소 Settings → Secrets and variables → Actions에 다음 Secrets를 등록한다:
   - `NAVER_IMAP_USER`
   - `NAVER_IMAP_APP_PASSWORD`
   - `ANTHROPIC_API_KEY`
   - `SLACK_WEBHOOK_URL`
3. `.github/workflows/daily-digest.yml`이 매일 08:00 KST(`cron: '0 23 * * *'` UTC)에 자동 실행된다.
4. 첫 실행은 반드시 **수동으로 검증**한다: GitHub 저장소 → Actions → "Daily Newsletter Digest" →
   **Run workflow** (workflow_dispatch)로 트리거한다. 확인할 것:
   - 실제 Slack 채널에 리포트가 도착하는지
   - 네이버 메일함에 `\Seen` 플래그 변경 외의 상태 변경(삭제/이동 등)이 없는지
   - `state/seen_urls.json`이 오늘자 URL을 포함해 커밋되었는지
   - 실행 시간이 10분 이내인지 (Actions 실행 로그의 소요 시간 확인)
   - Actions 로그에 자격증명 값이 노출되지 않는지
5. 이후에는 `schedule` cron 트리거가 자동으로 매일 실행하며 별도 개입이 필요 없다.

## 로그 확인

실행 로그는 GitHub Actions 콘솔에서 확인한다 (기본 90일 보관). 별도 로그 저장소/전송은 현재 범위 밖이다.

## 테스트

```bash
pytest tests/ -v
ruff check src/ tests/
```

`tests/unit`, `tests/exception`, `tests/integration` 세 종류로 구성되어 있으며, 실계정 자격증명 없이
전부 모킹으로 동작한다. push/PR 시 `.github/workflows/tests.yml`이 자동 실행한다.
