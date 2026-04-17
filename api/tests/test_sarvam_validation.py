from app.routers.sarvam import _is_predominantly_odia


def test_pure_odia():
    assert _is_predominantly_odia("ଓଡ଼ିଆ ଭାଷା")


def test_pure_english():
    assert not _is_predominantly_odia("English text only")


def test_mixed_majority_odia():
    assert _is_predominantly_odia("ଓଡ଼ିଆ text mix here ଭାଷା ଏକ")


def test_empty():
    assert not _is_predominantly_odia("")


def test_punctuation_only():
    assert not _is_predominantly_odia("...!?")
