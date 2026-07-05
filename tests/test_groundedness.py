"""Unit tests for the groundedness verifier (landfall/verify/groundedness.py).

The verifier is the load-bearing correctness boundary of the whole project — "the prompt
telling the narrator what numbers it may use is not itself a correctness guarantee ...
this module is the actual enforcement point." So its number parsing and matching are
tested here directly and exhaustively, deterministically (no API calls).

These are the regression tests for a real bug found by edge-case probing: abbreviated
magnitude figures ("$49.3M", "₱1.2B") silently bypassed the verifier entirely, because
extraction truncated them to 49.3 / 1.2, which then fell under the small-number (< 100)
exemption. A fabricated "$49.3M" therefore passed verification with zero flagged claims,
while the equivalent "$49.3 million" was correctly caught. The fix parses currency-
prefixed attached abbreviations, guarded against NDRRMC-corpus false positives (bare
"20m" = metres; "₱2,229,439.00 b" = a peso amount plus a list-marker) — see the cases
below and _NUMBER_RE's docstring.

Run without pytest: python tests/test_groundedness.py   (asserts, prints a summary)
Run with pytest if installed: pytest tests/test_groundedness.py
"""

from landfall.verify.groundedness import check, extract_numbers, redact_ungrounded


def test_plain_numbers_extracted():
    assert extract_numbers("49,327,691.86") == [49_327_691.86]
    assert extract_numbers("9,168,006 people") == [9_168_006]
    assert extract_numbers("293,000,000.00") == [293_000_000.0]
    assert extract_numbers("$49,327,691.86") == [49_327_691.86]  # currency prefix stripped


def test_spelled_out_magnitudes():
    assert extract_numbers("49.3 million") == [49_300_000]
    assert extract_numbers("1.2 billion") == [1_200_000_000]
    assert extract_numbers("500 thousand") == [500_000]
    assert extract_numbers("2.5 trillion") == [2_500_000_000_000]  # trillion added in fix


def test_magnitude_word_separators():
    # space, hyphen, or no separator between number and spelled-out word all work
    assert extract_numbers("49.3 million") == [49_300_000]
    assert extract_numbers("49.3-million") == [49_300_000]
    assert extract_numbers("49.3million") == [49_300_000]


def test_currency_prefixed_abbreviations_magnified():
    # the core fix: $/₱-prefixed, directly-attached single-letter suffix
    assert extract_numbers("$49.3M") == [49_300_000]
    assert extract_numbers("₱1.2B") == [1_200_000_000]
    assert extract_numbers("$695M") == [695_000_000]
    assert extract_numbers("₱400M") == [400_000_000]  # the one real token in the corpus
    assert extract_numbers("$825K") == [825_000]


def test_corpus_false_positive_guards():
    # bare single-letter suffix (no currency) must NOT be magnified — "20m"/"3.8m" are
    # metres in NDRRMC road-damage tables, not millions
    assert extract_numbers("20m") == [20.0]
    assert extract_numbers("3.8m") == [3.8]
    assert extract_numbers("100m culvert") == [100.0]
    # a complete currency amount followed by a space + list-marker "b." must read the
    # amount only, not magnify by the "b" — real token "₱2,229,439.00 b" from the corpus
    assert extract_numbers("₱2,229,439.00 b") == [2_229_439.00]


def test_bare_abbreviation_is_a_documented_gap():
    # deliberately NOT magnified: a bare "49.3M" (no currency prefix) still reads 49.3,
    # because "m" cannot be safely disambiguated from metres. Pinned so a future change
    # that "fixes" this also has to consciously accept the metres-collision risk.
    assert extract_numbers("49.3M USD") == [49.3]
    assert extract_numbers("49.3 M") == [49.3]  # space-separated bare suffix, also unmagnified


def test_check_grounds_within_tolerance():
    refs = [695_357_863.53, 9_329_251.0]
    # exact and within-1% both count as grounded
    assert check("damage was 695,357,863.53", refs).ungrounded == []
    assert check("about 695,000,000", refs).ungrounded == []  # 0.05% off -> grounded
    # outside tolerance -> flagged
    assert check("damage was 800,000,000", refs).total_claims == 1
    assert check("damage was 800,000,000", refs).ungrounded == ["800000000.0"]


def test_small_numbers_exempt():
    refs = [695_357_863.53]
    # only numbers < 100 (single/double-digit counts, category numbers) are exempt as
    # not-load-bearing; nothing >= 100 is
    report = check("Category 5 storm, 50 responders, 12 shelters set up.", refs)
    assert report.total_claims == 0


def test_year_is_a_claim_grounded_via_permitted_value():
    # a 4-digit year is >= 100, so it IS checked, not exempted — years are handled by
    # being passed as a permitted reference value (verified_narrator does exactly this
    # with permitted_values=[year]), not by the small-number exemption
    assert check("In 2013 the damage was 695,357,863.53.", [695_357_863.53, 2013]).ungrounded == []
    # without the year permitted, it is (correctly) flagged
    assert check("In 2013 the damage was 695,357,863.53.", [695_357_863.53]).ungrounded == ["2013.0"]


def test_abbreviated_fabrication_is_flagged():
    # the regression: true damage ~695M; a fabricated "$49.3M" (14x low) must be caught,
    # not silently exempted the way it was before the fix
    refs = [695_357_863.53, 9_329_251.0, 2013]
    assert check("The damage was approximately $49.3M.", refs).ungrounded == ["49300000.0"]
    assert check("The damage was about ₱1.2B.", refs).ungrounded == ["1200000000.0"]
    # a correct abbreviated figure (~695M) passes
    assert check("The damage was approximately $695.4M.", refs).ungrounded == []


def test_redaction_removes_abbreviated_fabrication():
    refs = [695_357_863.53]
    text = "The damage was $49.3M according to the model."
    redacted, report = redact_ungrounded(text, refs)
    assert "$49.3M" not in redacted
    assert "[REDACTED]" in redacted
    assert report.ungrounded == []  # nothing ungrounded survives redaction


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = []
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failures.append(t.__name__)
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
