"""The check for the two-helpers eval case. Green only if all three tasks landed
and compose correctly."""
from src.headline import headline


def test_headline_composes_slug_then_shout():
    assert headline("Hello World") == "HELLO-WORLD!"


def test_headline_strips_punctuation():
    assert headline("A, B & C!") == "A-B-C!"
