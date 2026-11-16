# Entity Resolution: Record Pair Scoring Engine

A deterministic, explainable Python solution for customer record linkage and deduplication, implemented for the Forward Deployed Engineer Intern screening task at Greyquill Software.

---

## 1. Project Purpose

In enterprise environments, customer records arrive from heterogeneous sources (POS terminals, call centres, loyalty apps, partner imports) with noise, typos, distinct formatting conventions, and missing attributes. 

This project implements a configurable pairwise scoring function, `score_pair`, to evaluate how likely two customer records belong to the same real-world person without blindly merging records that share superficial attributes (e.g., family members sharing a phone number or address).

---

## 2. How the Matching Engine Works

The core function evaluates two records according to a comparison plan (`list[FieldComparison]`):

$$\text{confidence} = \frac{\sum_{i \in \text{compared}} \text{score}_i \times \text{weight}_i}{\sum_{i \in \text{compared}} \text{weight}_i}$$

### Rules & Method Implementations

1. **Missing / Blank Handling:**
   - Any attribute that is missing (`None`), omitted, or whitespace-only on either side provides **no evidence**.
   - Missing fields are omitted from `field_scores` and excluded from both the numerator and denominator of the weighted average.
   - If no fields can be compared, `confidence = 0.0`, `algorithm = ""`, and `field_scores = {}`.

2. **`"exact"` (e.g. `pin_code`, `city`):**
   - Whitespace is stripped and casing ignored.
   - Returns `1.0` if values match, otherwise `0.0`.

3. **`"normalized_phone"` (e.g. `phone`):**
   - Strips `+91`, leading `0`, spaces, and hyphens.
   - All valid phone numbers in the dataset normalize to 10 digits.
   - Returns `1.0` if normalized numbers match, otherwise `0.0`.

4. **`"date"` (e.g. `date_of_birth`):**
   - Robustly parses common Indian enterprise formats:
     - ISO: `YYYY-MM-DD`
     - Slash: `DD/MM/YYYY`
     - Textual month: `DD-Mon-YYYY` (e.g. `02-Dec-1969`)
     - Two-digit year: `DD.MM.YY` (e.g. `18.10.87`, `09.12.68`)
   - **Historical Date Disambiguation:** Handles Python's standard `strptime` century boundary bug where two-digit years (such as `68` or `65`) default to 2068/2065. If a parsed year is in the future, it adjusts back 100 years.
   - Returns `1.0` if both dates represent the same calendar day; otherwise `0.0`.

5. **`"edit_distance"` (e.g. `email`):**
   - Implements normalized Levenshtein distance:
     $$\text{similarity} = 1.0 - \frac{\text{Levenshtein}(s_1, s_2)}{\max(\text{len}(s_1), \text{len}(s_2))}$$
   - Returns a continuous value from `0.0` to `1.0`.

6. **`"phonetic"` (e.g. `name`):**
   - Tokenizes names by splitting on whitespace, commas, and periods.
   - Order-invariant bipartite matching: finds the optimal assignment between tokens in record $A$ and record $B$.
   - Handles:
     - Name reordering: `"Patel, Fatima"` vs `"Fatima Patel"` &rarr; `1.000`
     - Initials: `"S. Bhat"` vs `"Swathi Bhat"` &rarr; `0.925`
     - Indian name phonetic variations: Soundex matching (`"Gurprit"` vs `"Gurpreet"`, `"Pooja"` vs `"Puja"`) &rarr; `> 0.950`
     - Typographical variations: edit distance fallback for minor typos.

7. **`algorithm` Output:**
   - A `+`-delimited string indicating which comparison methods produced the final score (e.g. `"phonetic+normalized_phone+date+exact+exact"`).

---

## 3. Important Design Decisions

- **Zero External Dependencies:** Built entirely with Python's standard library (`dataclasses`, `datetime`, `itertools`, `re`, `unittest`, `csv`). No external AI APIs, network calls, or C-extensions are required.
- **Explainability & Determinism:** Avoids black-box ML models. Every score can be directly audited and explained to stakeholders by inspecting `field_scores`.
- **Order-Invariant Name Matching:** Rather than relying on strict string similarity, token permutation matching naturally accommodates Indian naming conventions (where surnames frequently precede given names).
- **Two-Digit Year Correction:** Corrects Python's built-in 2-digit year mapping cutoff so that historical birthdates like `11.07.65` correctly match `11-Jul-1965`.

---

## 4. Known Limitations

1. **Shared Household Identifiers:**
   - Multiple family members often share a single phone number and postal code (e.g. parent and minor child). While our engine scores these fields accurately, downstream entity resolution must consider negative evidence (such as a 27-year age gap) before merging records.
2. **Email Domain Weighting:**
   - Standard Levenshtein distance on full email strings (`user1@example.com` vs `user2@example.com`) awards similarity for the shared domain name `@example.com`. Splitting username and domain could further sharpen email scoring.
3. **Soundex Phonetic Assumptions:**
   - Soundex was designed primarily for Anglo-Saxon names. While our token-level hybrid with edit distance handles Indian phonetics well, a language-tailored Indian phonetic algorithm (e.g., Metaphone variant) would handle complex retroflex consonants even better.

---

## 5. Installation Instructions

Requires Python 3.9 or higher.

```bash
# Clone or navigate to the repository
cd score-pair

# Verify Python version
python --version
```

No external package installation (`pip install`) is needed.

---

## 6. How to Run

### Run the Test Suite

```bash
python -m unittest test_score_pair.py -v
```

### Run on Selected Records

To compare two records from `customer-records.csv`:

```bash
python score_pair.py R0007 R0058
```

### Expected Output Format

```text
Scoring record R0007 vs R0058:
Record A (R0007): Ramesh Kumar | +91-9218161756 | 18.10.87 | bengaluru
Record B (R0058): Rahul Kumar | 9218161756 | 11-Oct-2014 | Bengaluru
------------------------------------------------------------
MatchResult:
  Confidence:   0.5938
  Algorithm:    phonetic+normalized_phone+date+exact+exact
  Field Scores: {'name': 0.5, 'phone': 1.0, 'date_of_birth': 0.0, 'pin_code': 1.0, 'city': 1.0}
```
