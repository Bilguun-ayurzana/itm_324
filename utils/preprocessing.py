import re
import unicodedata
from typing import List
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0

try:
    from .stopwords_mn import MN_STOPWORDS, MN_SUFFIXES 
except Exception:
    try:
        from stopwords_mn import MN_STOPWORDS, MN_SUFFIXES  
    except Exception:
        MN_STOPWORDS = set()
        MN_SUFFIXES = []

try:
    from .stopwords_en import EN_STOPWORDS
except Exception:
    try:
        from stopwords_en import EN_STOPWORDS
    except Exception:
        EN_STOPWORDS = set()

MN_SUFFIXES_SORTED = sorted(MN_SUFFIXES, key=len, reverse=True)
_MN_SPECIFIC_CHARS = set("ӨөҮүҢң")  


def _contains_mongolian_hint(text: str) -> bool:
    """
    Quick heuristic: return True if text contains characters that strongly indicate Mongolian
    (either Mongolian-specific Cyrillic letters or characters from the Mongolian script block).
    """
    if not text:
        return False
    for ch in text:
        if ch in _MN_SPECIFIC_CHARS:
            return True
        cp = ord(ch)
        if 0x1800 <= cp <= 0x18AF:
            return True
    return False


def detect_language(text: str) -> str:
    """
    Language detection with Mongolian fallback heuristics:
    - Samples token-like words from the input to reduce noise.
    - Uses langdetect first; if result is ambiguous/ru/unknown but heuristics detect Mongolian-specific
      characters, return 'mn'.
    """
    if not text or not text.strip():
        return "unknown"
    tokens = re.findall(r"\w+", text, flags=re.UNICODE)
    if not tokens:
        return "unknown"
    sample = " ".join(tokens[:200])
    try:
        lang = detect(sample)
    except Exception:
        lang = "unknown"

    
    if lang in ("unknown", "ru") and _contains_mongolian_hint(sample):
        return "mn"

    return lang


def mn_stem_word(word: str, min_stem_len: int = 3) -> str:
   
    if not word or len(word) <= min_stem_len:
        return word
    w = unicodedata.normalize("NFKC", word)
    for _ in range(3):  
        changed = False
        for suf in MN_SUFFIXES_SORTED:
            if suf and w.endswith(suf) and (len(w) - len(suf)) >= min_stem_len:
                w = w[:-len(suf)]
                changed = True
                break
        if not changed:
            break
    return w


def mn_preprocess(text: str) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    pattern = r"[^a-z0-9\u0400-\u052F\u2DE0-\u2DFF\uA640-\uA69F\u1800-\u18AF\s]"
    text = re.sub(pattern, " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def en_preprocess(text: str) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def mn_tokenize_and_stem(text: str, remove_stopwords: bool = True, min_stem_len: int = 3) -> List[str]:
    text = mn_preprocess(text)
    if not text:
        return []
    tokens = text.split()
    if remove_stopwords and MN_STOPWORDS:
        tokens = [t for t in tokens if t not in MN_STOPWORDS]
    tokens = [mn_stem_word(t, min_stem_len=min_stem_len) for t in tokens]
    return tokens


def en_tokenize(text: str, remove_stopwords: bool = True) -> List[str]:

    text = en_preprocess(text)
    if not text:
        return []
    tokens = text.split()
    if remove_stopwords and EN_STOPWORDS:
        tokens = [t for t in tokens if t not in EN_STOPWORDS]
    return tokens


def debug_removed_characters(sample: str) -> List[str]:
    if sample is None:
        return []
    sample_norm = unicodedata.normalize("NFKC", sample)
    allowed_re = re.compile(r"[a-z0-9\u0400-\u052F\u2DE0-\u2DFF\uA640-\uA69F\u1800-\u18AF\s]", flags=re.IGNORECASE)
    removed = sorted({ch for ch in sample_norm if not allowed_re.match(ch)})
    return removed


__all__ = [
    "detect_language",
    "mn_preprocess",
    "en_preprocess",
    "mn_tokenize_and_stem",
    "mn_stem_word",
    "en_tokenize",
    "debug_removed_characters",
]