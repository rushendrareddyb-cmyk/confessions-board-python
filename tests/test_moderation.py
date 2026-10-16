import pytest

from app.moderation import (
    MAX_BODY,
    RATE_LIMIT,
    RATE_WINDOW,
    ModerationError,
    burst_capacity,
    check_body,
    check_rate,
    collapse_runs,
    device_bucket,
    expand,
    find_blocked,
    is_clean,
    moderate,
    reports_needed,
    should_remoderate,
    status_after_report,
    tokenise,
    window_start,
)


# Word filter: blocked words and common disguises
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("stupid", ["stupid"]),
        ("STUPID", ["stupid"]),
        ("stup1d", ["stupid"]),
        ("$tupid", ["stupid"]),
        ("stuuupid", ["stupid"]),
        ("s.t.u.p.i.d", ["stupid"]),
        ("M0R0N!!", ["moron"]),
    ],
)
def test_find_blocked_catches_disguises(text, expected):
    assert find_blocked(text) == expected


@pytest.mark.parametrize(
    "word",
    ["classmate", "assignment", "analysis", "dumbbell"],
)
def test_innocent_words_pass(word):
    assert find_blocked(word) == []
    assert is_clean(word)


def test_find_blocked_returns_sorted_unique_matches():
    assert find_blocked("stupid loser, STUPID") == ["loser", "stupid"]


def test_collapse_runs():
    assert collapse_runs("stuuupid") == "stupid"
    assert collapse_runs("bookkeeper") == "bokeper"


def test_tokenise_splits_punctuation():
    assert tokenise("s.t.u.p.i.d") == ["s", "t", "u", "p", "i", "d"]


def test_expand_handles_substitutions():
    assert "stupid" in expand("stup1d")


def test_expand_limits_large_variant_sets():
    assert expand("1" * 10)


# Body validation and moderation
@pytest.mark.parametrize("body", ["", " ", "\n\t", None])
def test_check_body_rejects_empty_body(body):
    with pytest.raises(ModerationError):
        check_body(body)


def test_check_body_rejects_oversized_body():
    with pytest.raises(ModerationError, match="too long"):
        check_body("x" * (MAX_BODY + 1))


def test_check_body_accepts_maximum_body_length():
    body = "x" * MAX_BODY
    assert check_body(body) == body


def test_check_body_strips_surrounding_whitespace():
    assert check_body("  hello world  ") == "hello world"


def test_long_single_word_is_handled():
    word = "x" * 100
    result = moderate(word)
    assert result["status"] == "published"
    assert result["body"] == word


def test_moderate_holds_blocked_content():
    result = moderate("You are stup1d")

    assert result["status"] == "held"
    assert result["matched"] == ["stupid"]
    assert result["body"] == "You are stup1d"


def test_moderate_publishes_clean_content():
    result = moderate("  hello classmate  ")

    assert result == {
        "status": "published",
        "matched": [],
        "body": "hello classmate",
    }


# Report threshold rules
@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (-5, 3),
        (0, 3),
        (9, 3),
        (10, 4),
        (11, 4),
        (20, 5),
    ],
)
def test_reports_needed_at_score_boundaries(score, expected):
    assert reports_needed(score) == expected


def test_reports_needed_accepts_custom_parameters():
    assert reports_needed(12, base=4, divisor=5) == 6


@pytest.mark.parametrize(
    ("base", "divisor"),
    [(0, 10), (-1, 10), (3, 0), (3, -1)],
)
def test_reports_needed_rejects_invalid_parameters(base, divisor):
    with pytest.raises(ModerationError):
        reports_needed(0, base=base, divisor=divisor)


@pytest.mark.parametrize(
    ("reports", "score", "expected"),
    [
        (2, 0, False),
        (3, 0, True),
        (4, 0, True),
        (3, 10, False),
        (4, 10, True),
    ],
)
def test_should_remoderate_at_boundaries(reports, score, expected):
    assert should_remoderate(reports, score) is expected


@pytest.mark.parametrize(
    ("status", "reports", "score", "expected"),
    [
        ("held", 10, 0, "held"),
        ("rejected", 10, 0, "rejected"),
        ("published", 2, 0, "published"),
        ("published", 3, 0, "held"),
    ],
)
def test_status_after_report(status, reports, score, expected):
    assert status_after_report(status, reports, score) == expected


# Fixed-window rate limiting
def test_window_start():
    assert window_start(0) == 0
    assert window_start(599) == 0
    assert window_start(600) == 600


def test_window_start_rejects_invalid_window():
    with pytest.raises(ModerationError):
        window_start(100, window=0)


def test_check_rate_first_request():
    assert check_rate(0, now=0) == {
        "allowed": True,
        "used": 0,
        "limit": RATE_LIMIT,
        "remaining": RATE_LIMIT - 1,
        "reset_at": RATE_WINDOW,
        "retry_after": 0,
    }


def test_check_rate_last_allowed_request():
    result = check_rate(RATE_LIMIT - 1, now=100)

    assert result["allowed"] is True
    assert result["remaining"] == 0
    assert result["retry_after"] == 0


def test_check_rate_first_rejected_request():
    result = check_rate(RATE_LIMIT, now=100)

    assert result["allowed"] is False
    assert result["remaining"] == 0
    assert result["retry_after"] == RATE_WINDOW - 100


def test_retry_after_at_start_of_window():
    result = check_rate(RATE_LIMIT, now=600)

    assert result["reset_at"] == 1200
    assert result["retry_after"] == 600


def test_retry_after_at_end_of_window():
    result = check_rate(RATE_LIMIT, now=1199)

    assert result["reset_at"] == 1200
    assert result["retry_after"] == 1


def test_check_rate_normalizes_negative_usage():
    result = check_rate(-2, now=0)

    assert result["used"] == 0
    assert result["allowed"] is True


def test_check_rate_rejects_invalid_limit():
    with pytest.raises(ModerationError):
        check_rate(0, now=0, limit=0)


def test_check_rate_rejects_invalid_window():
    with pytest.raises(ModerationError):
        check_rate(0, now=0, window=0)


def test_burst_capacity_documents_fixed_window_limit():
    assert burst_capacity() == 2 * RATE_LIMIT
    assert burst_capacity(limit=3) == 6


# Anonymous device identifiers
def test_device_bucket_is_stable_for_same_salt():
    first = device_bucket("device-1", "salt-one")
    second = device_bucket("device-1", "salt-one")

    assert first == second


def test_device_bucket_changes_when_salt_changes():
    first = device_bucket("device-1", "salt-one")
    second = device_bucket("device-1", "salt-two")

    assert first != second


def test_device_bucket_trims_device_identifier():
    assert device_bucket(" device-1 ", "salt-one") == device_bucket(
        "device-1",
        "salt-one",
    )


@pytest.mark.parametrize("device_id", ["", " ", None])
def test_device_bucket_rejects_missing_device_id(device_id):
    with pytest.raises(ModerationError):
        device_bucket(device_id, "salt-one")
