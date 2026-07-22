"""
Clause segmentation. Honest admission up front (from the audit): this WILL
misfire on messy real-world contracts. Numbered/lettered sections are
detected first because they're the most reliable signal; everything else
degrades gracefully to paragraph and fixed-size chunking so we never return
zero clauses for a document that has real text.
"""
import re

MIN_CLAUSE_WORDS = 20
MAX_CLAUSE_TOKENS = 800  # approx via word count * 1.3
APPROX_TOKENS_PER_WORD = 1.3

# Matches: "1.", "1.1", "1.1.1", "A.", "(a)", "(i)", "Section 1", "Article 1", "ARTICLE I"
_NUMBERED_HEADING_RE = re.compile(
    r"^\s*(?:"
    r"(?:\d{1,2}(?:\.\d{1,2}){0,3}\.?)"      # 1, 1.1, 1.1.1
    r"|(?:[A-Z]\.)"                            # A.
    r"|(?:\([a-zA-Z]{1,3}\))"                  # (a), (iv)
    r"|(?:\([0-9]{1,3}\))"                     # (1)
    r"|(?:Section\s+\d+[A-Za-z]*)"
    r"|(?:Article\s+[IVXLCDM\d]+)"
    r")\s+\S",
    re.IGNORECASE,
)

# ALL CAPS heading line, e.g. "LIMITATION OF LIABILITY" (short, standalone line)
_CAPS_HEADING_RE = re.compile(r"^[A-Z][A-Z0-9 ,\-&/']{3,60}$")


def _approx_tokens(text: str) -> int:
    return int(len(text.split()) * APPROX_TOKENS_PER_WORD)


def _split_by_sentences(text: str) -> list[str]:
    # Simple sentence splitter — good enough for re-chunking oversized clauses,
    # not meant to be linguistically perfect.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_oversized(clause: str) -> list[str]:
    """Split a clause that exceeds MAX_CLAUSE_TOKENS at sentence boundaries."""
    if _approx_tokens(clause) <= MAX_CLAUSE_TOKENS:
        return [clause]

    sentences = _split_by_sentences(clause)
    chunks, current = [], []
    current_tokens = 0
    for sent in sentences:
        sent_tokens = _approx_tokens(sent)
        if current and current_tokens + sent_tokens > MAX_CLAUSE_TOKENS:
            chunks.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(sent)
        current_tokens += sent_tokens
    if current:
        chunks.append(" ".join(current))
    return chunks if chunks else [clause]


def _merge_short_fragments(clauses: list[str]) -> list[str]:
    """Merge fragments under MIN_CLAUSE_WORDS into the following clause,
    or the previous one if it's the last fragment."""
    merged: list[str] = []
    buffer = ""
    for clause in clauses:
        candidate = (buffer + " " + clause).strip() if buffer else clause
        if len(candidate.split()) < MIN_CLAUSE_WORDS:
            buffer = candidate
            continue
        merged.append(candidate)
        buffer = ""
    if buffer:
        if merged:
            merged[-1] = merged[-1] + " " + buffer
        else:
            merged.append(buffer)
    return merged


def _strategy_numbered_sections(text: str) -> list[str] | None:
    lines = text.split("\n")
    heading_indices = [i for i, line in enumerate(lines) if _NUMBERED_HEADING_RE.match(line.strip())]
    if len(heading_indices) < 3:
        return None  # not enough structure to trust this strategy

    clauses = []
    for idx, start in enumerate(heading_indices):
        end = heading_indices[idx + 1] if idx + 1 < len(heading_indices) else len(lines)
        chunk = "\n".join(lines[start:end]).strip()
        if chunk:
            clauses.append(chunk)
    return clauses if clauses else None


def _strategy_caps_headings(text: str) -> list[str] | None:
    lines = text.split("\n")
    heading_indices = [i for i, line in enumerate(lines) if _CAPS_HEADING_RE.match(line.strip())]
    if len(heading_indices) < 3:
        return None

    clauses = []
    for idx, start in enumerate(heading_indices):
        end = heading_indices[idx + 1] if idx + 1 < len(heading_indices) else len(lines)
        chunk = "\n".join(lines[start:end]).strip()
        if chunk:
            clauses.append(chunk)
    return clauses if clauses else None


def _strategy_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _strategy_fixed_chunk(text: str) -> list[str]:
    words = text.split()
    chunk_size = int(MAX_CLAUSE_TOKENS / APPROX_TOKENS_PER_WORD)
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]


def segment_clauses(text: str) -> list[str]:
    """
    Priority order:
      1. Numbered/lettered sections (most reliable when present)
      2. ALL CAPS / heading-style sections
      3. Paragraph breaks
      4. Fixed-size fallback chunking (guarantees non-empty output)
    """
    text = text.strip()
    if not text:
        return []

    raw_clauses = (
        _strategy_numbered_sections(text)
        or _strategy_caps_headings(text)
        or _strategy_paragraphs(text)
        or _strategy_fixed_chunk(text)
    )

    # Enforce max size (split oversized clauses)
    sized = []
    for clause in raw_clauses:
        sized.extend(_split_oversized(clause))

    # Enforce min size (merge undersized fragments)
    final = _merge_short_fragments(sized)

    return final
