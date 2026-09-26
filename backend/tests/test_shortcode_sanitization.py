"""Regression tests for sender-id sanitization.

Africa's Talking rejects any outbound SMS whose sender id/shortcode isn't a
single clean token ("InvalidSenderId"), but the raw values Bridge can end up
holding are not always clean:

- The SMS webhook's own "to" field can arrive with a shortcode and the
  recipient's number glued together (e.g. "57000+2349013004788").
- An AT_SHORTCODE env var can be copy-pasted straight from the Africa's
  Talking dashboard, which labels it like "Bridge (57000)" rather than just
  "57000".

``clean_sender_id`` (app.core.config) is the single place this is fixed, and
both the incoming-SMS trigger's ``_clean_shortcode`` and the outbound
``AfricaTalkingSMSProvider`` route through it.
"""
from app.core.config import clean_sender_id
from app.modules.workflows.nodes.trigger import _clean_shortcode


def test_strips_trailing_number_joined_with_plus():
    assert clean_sender_id("57000+2349013004788") == "57000"


def test_strips_trailing_number_joined_with_comma_or_space():
    assert clean_sender_id("57000,2349013004788") == "57000"
    assert clean_sender_id("57000 2349013004788") == "57000"


def test_extracts_code_from_dashboard_style_label():
    assert clean_sender_id("Bridge (57000)") == "57000"
    assert clean_sender_id("Bridge (57000)+2349013004788") == "57000"
    assert clean_sender_id("Bridge (57000)+2348023356028") == "57000"


def test_plain_shortcode_is_unchanged():
    assert clean_sender_id("57000") == "57000"


def test_blank_input_yields_blank():
    assert clean_sender_id("") == ""
    assert clean_sender_id(None) == ""


def test_trigger_shortcode_prefers_configured_value_over_webhook(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "at_shortcode", "Bridge (12345)")
    assert _clean_shortcode("57000+2349013004788") == "12345"


def test_trigger_shortcode_falls_back_to_webhook_value(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "at_shortcode", "")
    assert _clean_shortcode("57000+2349013004788") == "57000"
