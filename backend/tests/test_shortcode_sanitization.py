"""Regression test: Africa's Talking sometimes reports the SMS webhook's
"to" field as several values glued together (e.g. a shortcode and the
recipient's own number joined with "+"). Sending a reply with that raw
value as the sender id gets rejected outright ("InvalidSenderId"), so only
a clean, single token should ever reach the outbound SMS call.
"""
from app.modules.workflows.nodes.trigger import _clean_shortcode


def test_strips_trailing_number_joined_with_plus():
    assert _clean_shortcode("57000+2349013004788") == "57000"


def test_strips_trailing_number_joined_with_comma_or_space():
    assert _clean_shortcode("57000,2349013004788") == "57000"
    assert _clean_shortcode("57000 2349013004788") == "57000"


def test_plain_shortcode_is_unchanged():
    assert _clean_shortcode("57000") == "57000"


def test_blank_input_yields_blank():
    assert _clean_shortcode("") == ""


def test_configured_shortcode_wins_over_the_webhook_value(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "at_shortcode", "12345")
    assert _clean_shortcode("57000+2349013004788") == "12345"
