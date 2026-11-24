def detect_keywords(transcript: str, keywords: list[str]) -> list[str]:
    """Return one entry for each occurrence of every configured keyword."""
    normalized_transcript = transcript.lower()
    normalized_keywords = [keyword.lower().strip() for keyword in keywords if keyword and keyword.strip()]
    found = []
    seen = set()

    for keyword in normalized_keywords:
        if keyword in seen:
            continue
        seen.add(keyword)
        found.extend([keyword] * normalized_transcript.count(keyword))

    return found
