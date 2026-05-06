"""Tests for the Gupshup inbound payload classifier."""
from app.services.whatsapp.classifier import classify, MessageKind


def test_classify_button_reply():
    payload = {
        "type": "interactive",
        "interactive": {
            "type": "button_reply",
            "button_reply": {"id": "submit_thread"},
        },
    }
    assert classify(payload) == MessageKind.BUTTON


def test_classify_quoted_reply_text():
    payload = {
        "type": "text",
        "context": {"id": "wamid.HBgMabc"},
        "text": {"body": "correction: BJP won 4"},
    }
    assert classify(payload) == MessageKind.QUOTED_REPLY


def test_classify_quoted_reply_image():
    """A quoted reply with an image attachment is still a quoted reply."""
    payload = {
        "type": "image",
        "context": {"id": "wamid.HBgMabc"},
        "image": {"id": "media123"},
    }
    assert classify(payload) == MessageKind.QUOTED_REPLY


def test_classify_text_forward():
    payload = {"type": "text", "text": {"body": "Bypoll results announced..."}}
    assert classify(payload) == MessageKind.FORWARD


def test_classify_image_forward():
    payload = {"type": "image", "image": {"id": "media123"}}
    assert classify(payload) == MessageKind.FORWARD


def test_classify_document_forward():
    payload = {"type": "document", "document": {"id": "doc123", "filename": "report.pdf"}}
    assert classify(payload) == MessageKind.FORWARD


def test_classify_audio_forward():
    payload = {"type": "audio", "audio": {"id": "aud123"}}
    assert classify(payload) == MessageKind.FORWARD


def test_classify_video_forward():
    payload = {"type": "video", "video": {"id": "vid123"}}
    assert classify(payload) == MessageKind.FORWARD


def test_classify_sticker_skip():
    payload = {"type": "sticker"}
    assert classify(payload) == MessageKind.SKIP_STICKER


def test_classify_location_skip():
    payload = {"type": "location"}
    assert classify(payload) == MessageKind.SKIP_LOCATION


def test_classify_contact_skip():
    payload = {"type": "contacts"}
    assert classify(payload) == MessageKind.SKIP_CONTACT


def test_classify_unknown_type_falls_to_skip_other():
    assert classify({"type": "video_note"}) == MessageKind.SKIP_OTHER


def test_classify_missing_type_falls_to_skip_other():
    assert classify({}) == MessageKind.SKIP_OTHER
