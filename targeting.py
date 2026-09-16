"""
Generic target-string resolution against (id, keywords) candidates.

Domain-agnostic: knows nothing about NPCs, players, rooms, or items.
Callers build a list of (id, keywords) pairs for whatever domain they're
targeting and hand it to resolve_target() along with the raw player input.

Matching rules:
  - Keyword comparison is case-insensitive and exact-match only (no
    prefix or substring matching).
  - Optional "N." ordinal prefix selects the Nth match among candidates
    whose keywords contain the given word, in input list order.
    Bare input (no "N." prefix) defaults to ordinal 1.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedTarget:
    ordinal: int
    keyword: str


@dataclass(frozen=True)
class TargetResolution:
    found: bool
    id: int | None = None
    # Set when found=False and at least one candidate matched the keyword,
    # but not at the requested ordinal. Lets the caller distinguish
    # "no such thing here" from "not that many of them here".
    ordinal_out_of_range: bool = False
    matched_count: int = 0


def parse_target(raw: str) -> ParsedTarget:
    """
    Parse "2.goblin" -> ParsedTarget(ordinal=2, keyword="goblin").
    Parse "goblin"   -> ParsedTarget(ordinal=1, keyword="goblin").

    Malformed ordinal prefixes (e.g. "x.goblin", "0.goblin", ".goblin")
    are treated as a literal keyword with no ordinal split — the whole
    string becomes the keyword, ordinal defaults to 1. This keeps parsing
    forgiving rather than rejecting input outright; callers can still get
    a "not found" result naturally if the literal string never matches.
    """
    raw = raw.strip().lower()

    if "." in raw:
        prefix, _, rest = raw.partition(".")
        if prefix.isdigit() and rest:
            ordinal = int(prefix)
            if ordinal >= 1:
                return ParsedTarget(ordinal=ordinal, keyword=rest)

    return ParsedTarget(ordinal=1, keyword=raw)


def resolve_target(
    raw: str,
    candidates: list[tuple[int, list[str]]],
) -> TargetResolution:
    """
    Resolve a raw target string against a list of (id, keywords) pairs.

    keywords in each candidate should already be lowercased (callers that
    precompute effective_keywords at load time get this for free).
    """
    parsed = parse_target(raw)

    matches = [
        cand_id
        for cand_id, keywords in candidates
        if parsed.keyword in keywords
    ]

    if not matches:
        return TargetResolution(found=False, matched_count=0)

    index = parsed.ordinal - 1
    if index >= len(matches):
        return TargetResolution(
            found=False,
            ordinal_out_of_range=True,
            matched_count=len(matches),
        )

    return TargetResolution(found=True, id=matches[index], matched_count=len(matches))