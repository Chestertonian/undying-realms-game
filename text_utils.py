"""
Domain-agnostic text helpers: naive English pluralization and
number-to-words conversion. No knowledge of NPCs, items, or any other
domain — callers supply overrides where naive rules get it wrong.
"""

from __future__ import annotations

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
]
_TENS = [
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
    "eighty", "ninety",
]


def pluralize(word: str, override: str | None = None) -> str:
    """
    Return the plural form of `word`. If `override` is provided
    (non-empty), it's returned as-is — callers are expected to pass an
    author-supplied override for irregular plurals (e.g. "elf" -> "elves")
    rather than relying on these naive suffix rules for every case.

    Naive rules cover regular English pluralization only:
      - ends in s/x/z/ch/sh -> + es
      - consonant + y -> drop y, + ies
      - otherwise -> + s
    """
    if override:
        return override

    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"

    if word.endswith("y") and len(word) >= 2 and word[-2] not in "aeiou":
        return word[:-1] + "ies"

    return word + "s"


def _under_thousand_to_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")
    hundreds, rest = divmod(n, 100)
    result = f"{_ONES[hundreds]} hundred"
    if rest:
        result += f" {_under_thousand_to_words(rest)}"
    return result


def number_to_words(n: int) -> str:
    """
    Convert a non-negative integer to its English word form, e.g.
    2 -> "two", 21 -> "twenty-one", 1000 -> "one thousand".

    Handles 0 through 999,999. Falls back to the numeral string for
    anything larger or negative, rather than raising — a display
    function shouldn't crash a room description over an edge case.
    """
    if n < 0 or n > 999_999:
        return str(n)

    if n == 0:
        return _ONES[0]

    if n < 1000:
        return _under_thousand_to_words(n)

    thousands, rest = divmod(n, 1000)
    result = f"{_under_thousand_to_words(thousands)} thousand"
    if rest:
        result += f" {_under_thousand_to_words(rest)}"
    return result