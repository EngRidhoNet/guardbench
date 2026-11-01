def classify(text: str) -> dict[str, str]:
    lowered = text.lower()
    if any(term in lowered for term in ("steal", "bypass", "malware", "password")):
        return {"decision": "block", "reason": "Matched restricted request rule"}
    if any(term in lowered for term in ("which investment", "legal advice", "diagnose me")):
        return {"decision": "escalate", "reason": "Human expertise required"}
    return {"decision": "allow", "reason": "Educational request"}
