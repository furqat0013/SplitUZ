import pytest

from app.services import parse_date, parse_deleted, parse_money, parse_settlement_status


@pytest.mark.parametrize("value", ["yo'q", "yo‘q", "yoʻq", "yo’q", "YO'Q", " yoq ", "no", "0", "false"])
def test_not_deleted_apostrophe_variants(value):
    assert parse_deleted(value) is False


@pytest.mark.parametrize("value", ["ha", "HA", "yes", "1", "true", "o‘chirilgan"])
def test_deleted_variants(value):
    assert parse_deleted(value) is True


def test_unknown_deleted_flag_fails_visibly():
    with pytest.raises(ValueError):
        parse_deleted("bilmadim")


@pytest.mark.parametrize("value", ["tasdiqlangan", "Tasdiqlangan", "TASDIQLANDI", "confirmed", " ok "])
def test_confirmed_status_variants(value):
    assert parse_settlement_status(value) == "tasdiqlangan"


@pytest.mark.parametrize("raw,expected", [("479400", 479400), ("479400.00", 479400), ("479 400", 479400), ("1,234", 1234)])
def test_integral_money_formats(raw, expected):
    assert parse_money(raw, "test") == expected


def test_fractional_som_is_rejected():
    with pytest.raises(ValueError):
        parse_money("10.50", "test")


@pytest.mark.parametrize("raw", ["2026-03-13", "13.03.2026", "13/03/2026", "2026/03/13"])
def test_date_formats(raw):
    assert parse_date(raw, "test").isoformat() == "2026-03-13"
