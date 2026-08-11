import settings


def test_encode_produces_four_bytes_with_magic_and_version():
    raw = settings.encode(1234)
    assert len(raw) == 4
    assert raw[0] == settings.MAGIC
    assert raw[1] == settings.VERSION


def test_encode_decode_round_trip():
    assert settings.decode(settings.encode(1234)) == 1234


def test_decode_rejects_bad_magic():
    raw = bytearray(settings.encode(1234))
    raw[0] = 0x00
    assert settings.decode(bytes(raw)) is None


def test_decode_rejects_unknown_version():
    raw = bytearray(settings.encode(1234))
    raw[1] = 0x99
    assert settings.decode(bytes(raw)) is None


def test_decode_rejects_short_buffer():
    assert settings.decode(b"\x67\x01") is None


def test_encode_rejects_out_of_range():
    for bad in (-1, 65536):
        try:
            settings.encode(bad)
        except ValueError:
            continue
        raise AssertionError("expected ValueError for %d" % bad)


def test_load_and_save_against_fake_nvm():
    nvm = bytearray(64)
    assert settings.load(nvm) is None
    settings.save(nvm, 850)
    assert settings.load(nvm) == 850
