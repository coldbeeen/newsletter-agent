from newsletter_agent.models import Article


def merge_same_day(articles: list[Article]) -> list[Article]:
    """동일 정규화 URL을 가진 기사를 병합한다.

    여러 뉴스레터에 같은 기사가 등장하면 출처를 모두 병기하고 요약은 하나만 유지한다.
    fetch에 성공한 요약이 있으면 그것을 우선하고(등장 순서상 먼저 성공한 것), 전부
    실패했을 경우에만 발췌 기반 요약(맨 처음 항목의 요약)을 유지한다.
    """
    merged_by_url: dict[str, Article] = {}
    order: list[str] = []

    for article in articles:
        key = article.normalized_url
        if key not in merged_by_url:
            merged_by_url[key] = article
            order.append(key)
            continue

        existing = merged_by_url[key]
        existing.source_newsletters.extend(article.source_newsletters)

        existing_ok = existing.fetch_result.status == "ok"
        incoming_ok = article.fetch_result.status == "ok"
        if incoming_ok and not existing_ok:
            # 기존 항목이 실패였고 새 항목이 성공이면 성공 쪽 요약으로 교체(출처는 유지).
            sources = existing.source_newsletters
            article.source_newsletters = sources
            merged_by_url[key] = article

    return [merged_by_url[key] for key in order]
