# 이슈 조사 기록 (2026-08-12)

사용자 보고 3건에 대한 근본원인 조사 결과. GitHub Actions 실제 실행 로그(26일치)와
임시 진단 워크플로(IMAP 직접 조회, 파이프라인 재현)로 검증 완료.

## 1. TLDR 계열 뉴스레터가 전혀 요약되지 않음

**증상**: 최근 26일간의 모든 데일리 다이제스트 실행 로그에 TLDR 관련 처리가 단 한 번도
등장하지 않음. IMAP 검색으로는 TLDR 메일이 정상적으로 매일 4~5통씩 수신되고 있었음.

**조사 경로**:
- IMAP FROM 검색: 정상 (`dan@tldrnewsletter.com`, 5통, 0 parse error)
- `Whitelist.classify()`의 표시이름 분류: 정상 (TLDR/TLDR IT/TLDR AI/TLDR Marketing/TLDR Data 모두 정확히 매칭)
- `mail_client.fetch_recent()`가 사용하는 `since_date_kst` 재현: 정상 (해당 날짜 메일이 검색됨)
- `extract_body_region()` + `extract_candidate_links()` 직접 실행 → **`extracted_links=0`**
  (footer trim을 끄면 `links_without_trim=26~38`로 정상 추출됨)

**근본원인**: `src/newsletter_agent/parsing/html_body.py`의 `_trim_footer()`가 footer
마커(`"unsubscribe"` 등)를 포함한 텍스트 노드를 찾으면, 그 조상을 `soup.body`의
**직계 자식**이 될 때까지 타고 올라간 뒤, 그 지점부터 이후 형제 요소를 전부 삭제한다.

TLDR의 HTML은 이메일 클라이언트 호환을 위한 전형적인 **테이블 중첩 레이아웃**
(`<body><table>...전체 콘텐츠(헤더/기사/광고/푸터)...</table></body>`)을 사용한다.
따라서 문서 맨 끝(전체 길이의 약 98% 지점)에 있는 실제 unsubscribe 링크의 조상을
타고 올라가면 **body의 유일한 직계 자식 = 이메일 전체를 감싸는 최상위 테이블**에
도달하게 되고, `marker_ancestor.decompose()`가 **본문 전체(기사 링크 26~38개 전부
포함)를 삭제**해버린다.

GeekNews(`news@hada.io`)나 routinecrew는 HTML 구조가 달라 이 문제를 우연히 피해갔다.

**검증 방법**: 실제 수신 메일 5통 모두에서 `extracted_links=0`,
`footer_marker_found='unsubscribe'`, `marker_char_pos`가 문서 끝 근처(전체 길이의
95% 이상) 확인. footer trim을 끄면 즉시 26~38개 링크가 추출됨.

**수정**: `_trim_footer()`가 조상을 타고 올라가는 범위를 `<body>` 직계 자식이 아니라
가장 가까운 블록 레벨 태그(`tr`, `td`, `th`, `li`, `p`, `div`, `tbody`, `table`)까지로
제한했다 (`html_body.py`의 `_BLOCK_LEVEL_TAGS`). 테스트:
`tests/unit/test_html_body.py::test_footer_trim_keeps_article_links_in_table_layout_email`.

---

## 2. GeekNews 기사 본문 접근 실패가 많음

**증상**: `Fetch blocked (bot-detection marker)` 로그가 GeekNews 기사에서 반복 발생.

**근본원인 (2가지 복합)**:

1. **잘못된 링크 대상**: GeekNews Weekly 뉴스레터의 기사 링크는 실제 원문 기사 URL이
   아니라 hada.io 자체 토픽 페이지(`news.hada.io/topic?id=NNNNN`)를 가리킨다. 이 페이지는
   원문에 대한 hada.io 커뮤니티의 요약·코멘트 페이지이며, 실제 원문 링크
   (예: `canva.dev/blog/...`)는 그 페이지 **안에** 별도로 존재한다. 현재 코드는 이
   중간 페이지를 그대로 "기사 본문"으로 fetch하려고 시도한다.

2. **봇 차단 오탐(false positive)**: `article_fetch.py`의 `_BLOCKED_BODY_MARKERS =
   ("cloudflare", "access denied", "checking your browser", "captcha")`가 응답 본문에
   대한 단순 문자열 포함 검사다. hada.io 토픽 페이지 자체가 "Cloudflare로 봇을 막는 방법"
   같은 **정상적인 기술 아티클**일 경우, 본문에 "Cloudflare"/"CAPTCHA" 단어가 주제상
   반복 등장하여 실제로는 차단되지 않았는데도 `status="blocked"`로 오판된다.

**검증 방법**: 실제 hada.io topic 페이지(`?id=32244`)를 직접 fetch해 본문에
"Cloudflare"(31회), "CAPTCHA"(8회) 문자열이 포함된 정상 콘텐츠임을 확인. 페이지 자체에는
실제 차단을 나타내는 정황(무한 리다이렉트, JS 챌린지 응답 등)이 없었음.

**수정 (2가지)**:
1. `_BLOCKED_BODY_MARKERS`를 "cloudflare"/"captcha" 같은 주제어 단독 매칭에서
   실제 차단 페이지에서만 나타나는 구체적 문구(`access denied`, `checking your browser`,
   `verify you are human`, `enable javascript and cookies to continue`, `ray id`)로 좁혔다.
2. `fetch_article()`이 hada.io 도메인(`*.hada.io`)의 응답을 받으면, 페이지 안의
   `class="topic-title-link"` 앵커(hada.io 웹 UI에서 원문 링크에 실제로 쓰이는 CSS 클래스)를
   찾아 그 URL로 한 번 더 fetch해 원문 본문을 가져온다 (`article_fetch.py`의
   `_find_hada_io_original_link`).

테스트: `tests/unit/test_article_fetch.py`의
`test_fetch_article_about_cloudflare_topic_not_classified_as_blocked`,
`test_fetch_article_hada_topic_page_follows_to_original_article`.

---

## 3. Slack 리포트 출력 포맷이 가독성이 낮음

**증상**: 리포트를 Slack Incoming Webhook에 `{"text": markdown_report}`로 그대로
전송하고 있었음. Slack은 표준 마크다운(`#`, `##`, `[텍스트](url)`)을 지원하지 않고
자체 mrkdwn 문법(`*굵게*`, `<url|텍스트>`)을 사용하므로, 실제 Slack 채널에는 `#`, `##`,
`[...]（...)` 기호가 그대로 텍스트로 노출되어 가독성이 크게 떨어지고 있었음.

**수정**: `report_synthesis.py`에 `compose_slack_blocks()`를 추가해 Slack Block Kit
형식(header/section/divider/context 블록, mrkdwn 링크 `<url|텍스트>`)으로 리포트를
구성하도록 했다. 콘솔 출력(`--console`)은 기존 마크다운 포맷(`compose_markdown_report`)을
그대로 유지한다. `delivery/slack.py`의 `send_to_slack()`은
`(webhook_url, blocks, fallback_text)`를 받아 `{"blocks": blocks, "text": fallback_text}`로
전송하도록 시그니처를 변경했다 (fallback_text는 알림 미리보기/접근성용).

테스트: `tests/unit/test_report_synthesis.py`, `tests/unit/test_slack_delivery.py`,
`tests/integration/test_pipeline_report.py`.

---

## 조사에 사용한 방법

- GitHub Actions 최근 26회 실행 로그 전수 조사 (TLDR 언급 0건 확인)
- 임시 진단 워크플로(`diagnose-imap.yml` + `scripts/diagnose_imap.py`, 조사 후 삭제)로:
  - IMAP FROM+SINCE 검색 직접 재현
  - 파이프라인과 동일한 `since_date_kst` 계산 재현
  - `extract_body_region`/`extract_candidate_links`를 실제 수신 메일에 직접 적용
  - footer marker 위치와 주변 컨텍스트 출력
- `newsletter-agent --console`을 실제 GitHub Actions 환경에서 실행해 파이프라인
  전체 동작 재현 (부수효과: 메일 읽음 처리, 실행 후 워크플로/스크립트는 제거함)
