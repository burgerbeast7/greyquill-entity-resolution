"""Starter file for Part 1 of the forward deployed engineer intern task.

Fill in score_pair. Keep the two classes and the function signature as they are, because we
run our own tests against them. Add any helpers and libraries you need, and list the
libraries in your README.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import itertools
import re


@dataclass
class FieldComparison:
    """How to compare one field."""

    attribute: str  # a column name, such as "phone"
    method: str  # "phonetic", "edit_distance", "normalized_phone", "exact" or "date"
    weight: float


@dataclass
class MatchResult:
    confidence: float  # 0.0 to 1.0
    algorithm: str  # which methods produced the score, such as "phonetic+normalized_phone"
    field_scores: dict[str, float]  # one score from 0.0 to 1.0 for each field that was compared


# The plan we use for customer-records.csv. You may try others, but our tests use this one.
PLAN = [
    FieldComparison("name", "phonetic", 0.25),
    FieldComparison("email", "edit_distance", 0.20),
    FieldComparison("phone", "normalized_phone", 0.20),
    FieldComparison("date_of_birth", "date", 0.20),
    FieldComparison("pin_code", "exact", 0.10),
    FieldComparison("city", "exact", 0.05),
]


def _is_blank(val: object) -> bool:
    """Return True if a value is None or an empty/whitespace-only string."""
    if val is None:
        return True
    return str(val).strip() == ""


def _normalize_phone_str(val: object) -> str:
    """Strip +91, a leading 0, spaces, and hyphens."""
    s = str(val).strip()
    s = re.sub(r"[\s\-]+", "", s)
    if s.startswith("+91"):
        s = s[3:]
    elif s.startswith("91") and len(s) == 12:
        s = s[2:]
    if s.startswith("0"):
        s = s[1:]
    return s


def _compare_normalized_phone(a: object, b: object) -> float:
    """Compare two phone numbers after normalization."""
    norm_a = _normalize_phone_str(a)
    norm_b = _normalize_phone_str(b)
    if not norm_a or not norm_b:
        return 0.0
    return 1.0 if norm_a == norm_b else 0.0


def _parse_date(val: object) -> date | None:
    """Parse date from common formats in customer data, adjusting 2-digit years."""
    if _is_blank(val):
        return None
    s = str(val).strip()
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d.%m.%y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d.%m.%Y",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt).date()
            # Handle 2-digit year interpretation: historical birth dates cannot be in the future.
            # Python's strptime maps 00-68 to 2000-2068; adjust future years back 100 years.
            if dt.year > 2024:
                dt = dt.replace(year=dt.year - 100)
            return dt
        except (ValueError, OverflowError):
            continue
    return None


def _compare_date(a: object, b: object) -> float:
    """Compare two calendar dates."""
    date_a = _parse_date(a)
    date_b = _parse_date(b)
    if date_a is None or date_b is None:
        return 0.0
    return 1.0 if date_a == date_b else 0.0


def _compare_exact(a: object, b: object) -> float:
    """Compare values after trimming spaces and ignoring case."""
    str_a = str(a).strip().lower()
    str_b = str(b).strip().lower()
    return 1.0 if str_a == str_b else 0.0


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute the Levenshtein edit distance between two strings."""
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _compare_edit_distance(a: object, b: object) -> float:
    """Normalized edit distance similarity between 0.0 and 1.0."""
    str_a = str(a).strip().lower()
    str_b = str(b).strip().lower()
    if not str_a and not str_b:
        return 1.0
    max_len = max(len(str_a), len(str_b))
    if max_len == 0:
        return 1.0
    dist = _levenshtein_distance(str_a, str_b)
    return max(0.0, min(1.0, 1.0 - (dist / max_len)))


def _soundex(token: str) -> str:
    """Compute American Soundex code for a word token."""
    token = token.upper()
    if not token or not token[0].isalpha():
        return ""
    mapping = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }
    first = token[0]
    res = [first]
    prev = mapping.get(first, "0")
    for ch in token[1:]:
        code = mapping.get(ch, "0")
        if code != "0":
            if code != prev:
                res.append(code)
            prev = code
        else:
            prev = "0"
    return ("".join(res) + "000")[:4]


def _token_similarity(t1: str, t2: str) -> float:
    """Compare two single name tokens handling exact matches, initials, and phonetics."""
    t1 = t1.lower()
    t2 = t2.lower()
    if t1 == t2:
        return 1.0

    # Initial match: an initial matching the prefix of a full name (e.g. 's' vs 'swathi')
    if (len(t1) == 1 and t2.startswith(t1)) or (len(t2) == 1 and t1.startswith(t2)):
        return 0.85

    # Phonetic similarity via Soundex with edit distance refinement
    s1, s2 = _soundex(t1), _soundex(t2)
    e_sim = _compare_edit_distance(t1, t2)
    if s1 and s2 and s1 == s2:
        return 0.90 + 0.10 * e_sim

    # Typographical similarity for minor misspellings/transpositions not caught by Soundex
    if e_sim >= 0.70:
        return e_sim

    return 0.0


def _compare_phonetic(a: object, b: object) -> float:
    """Compare names across reordering, case variations, initials, and phonetics."""
    toks_a = [t for t in re.split(r"[\s,\.]+", str(a).strip()) if t]
    toks_b = [t for t in re.split(r"[\s,\.]+", str(b).strip()) if t]
    if not toks_a or not toks_b:
        return 0.0

    # Ensure toks_a is the smaller or equal list
    swapped = False
    if len(toks_a) > len(toks_b):
        toks_a, toks_b = toks_b, toks_a
        swapped = True

    best_match_score = 0.0
    # Optimal bipartite matching over all permutations of toks_b for toks_a
    for perm in itertools.permutations(toks_b, len(toks_a)):
        score = sum(_token_similarity(t1, t2) for t1, t2 in zip(toks_a, perm))
        if score > best_match_score:
            best_match_score = score

    # Normalize by the max token count so omitted tokens reduce confidence
    max_tokens = max(len(toks_a), len(toks_b))
    return max(0.0, min(1.0, best_match_score / max_tokens))


def score_pair(a: dict[str, object], b: dict[str, object], plan: list[FieldComparison]) -> MatchResult:
    """Return how likely records a and b belong to the same person.

    What we expect:
      - A blank or missing value on either side gives no evidence. Leave that field out of
        field_scores and out of the weighted average.
      - confidence is the weighted average of the field scores that were compared, so it is
        always between 0.0 and 1.0. If nothing could be compared, it is 0.0.
      - "normalized_phone": 1.0 when the numbers are the same after removing +91, a leading 0,
        spaces and hyphens. Otherwise 0.0.
      - "date": 1.0 when both values are the same calendar date, in any of the formats in the
        file. Otherwise 0.0.
      - "exact": 1.0 when the values are equal after trimming spaces and ignoring case.
        Otherwise 0.0.
      - "phonetic" and "edit_distance": a similarity from 0.0 to 1.0 that you choose and
        explain. A name written in a different order, case or with an initial should still
        score well against the full name.
    """
    field_scores: dict[str, float] = {}
    total_weighted_score = 0.0
    total_weight = 0.0
    methods_used: list[str] = []

    for fc in plan:
        val_a = a.get(fc.attribute)
        val_b = b.get(fc.attribute)

        # A blank or missing value on either side gives no evidence
        if _is_blank(val_a) or _is_blank(val_b):
            continue

        if fc.method == "phonetic":
            score = _compare_phonetic(val_a, val_b)
        elif fc.method == "edit_distance":
            score = _compare_edit_distance(val_a, val_b)
        elif fc.method == "normalized_phone":
            score = _compare_normalized_phone(val_a, val_b)
        elif fc.method == "date":
            score = _compare_date(val_a, val_b)
        elif fc.method == "exact":
            score = _compare_exact(val_a, val_b)
        else:
            raise ValueError(f"Unknown comparison method: {fc.method}")

        field_scores[fc.attribute] = score
        total_weighted_score += score * fc.weight
        total_weight += fc.weight
        methods_used.append(fc.method)

    if total_weight > 0.0:
        confidence = total_weighted_score / total_weight
    else:
        confidence = 0.0

    algorithm = "+".join(methods_used)

    return MatchResult(confidence=confidence, algorithm=algorithm, field_scores=field_scores)


if __name__ == "__main__":
    import csv
    import sys

    # Default record IDs to demo, or accept via command line arguments
    id_a = sys.argv[1] if len(sys.argv) > 1 else "R0007"
    id_b = sys.argv[2] if len(sys.argv) > 2 else "R0058"
    csv_file = sys.argv[3] if len(sys.argv) > 3 else "customer-records.csv"

    records = {}
    try:
        with open(csv_file, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                records[row["record_id"]] = row
    except FileNotFoundError:
        print(f"Error: {csv_file} not found.")
        sys.exit(1)

    if id_a not in records or id_b not in records:
        print(f"Error: Record IDs {id_a} and/or {id_b} not found in {csv_file}.")
        sys.exit(1)

    rec_a, rec_b = records[id_a], records[id_b]
    result = score_pair(rec_a, rec_b, PLAN)

    print(f"Scoring record {id_a} vs {id_b}:")
    print(f"Record A ({id_a}): {rec_a['name']} | {rec_a['phone']} | {rec_a['date_of_birth']} | {rec_a['city']}")
    print(f"Record B ({id_b}): {rec_b['name']} | {rec_b['phone']} | {rec_b['date_of_birth']} | {rec_b['city']}")
    print("-" * 60)
    print(f"MatchResult:")
    print(f"  Confidence:   {result.confidence:.4f}")
    print(f"  Algorithm:    {result.algorithm}")
    print(f"  Field Scores: {result.field_scores}")

