from difflib import SequenceMatcher

def fuzzy_match(a: str, b: list, threshold: float = 0.7) -> bool:
    return any(SequenceMatcher(None, a.lower(), x.lower()).ratio() >= threshold for x in b)
