# tests/unit/test_scoring_core.py

from scoring.core import get_score


def test_score_phone_only():
    assert get_score(phone="123", email=None) == 1.5


def test_score_phone_and_email():
    assert get_score(phone="123", email="a@b.c") == 3.0


def test_score_empty():
    assert get_score(None, None) == 0
