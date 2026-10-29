import pytest

from app.domain.recovery_code import (
    ALPHABET,
    CODE_LENGTH,
    format_recovery_code,
    is_well_formed,
    normalize_recovery_code,
)

RAW = "K7QMX2PD9WFA3HTR"


def test_T_DOM_RECOV_01_normalize_ignores_case_hyphens_and_spaces():
    assert normalize_recovery_code("k7qm-x2pd-9wfa-3htr") == RAW
    assert normalize_recovery_code(" K7QM X2PD 9WFA 3HTR ") == RAW
    assert normalize_recovery_code(RAW) == RAW


def test_T_DOM_RECOV_02_format_groups_of_four():
    assert format_recovery_code(RAW) == "K7QM-X2PD-9WFA-3HTR"


def test_T_DOM_RECOV_03_alphabet_has_32_symbols_without_look_alikes():
    assert len(set(ALPHABET)) == 32
    assert not set("01IO") & set(ALPHABET)


def test_T_DOM_RECOV_03_well_formed_accepts_a_full_code():
    assert is_well_formed(RAW)
    assert is_well_formed("k7qm-x2pd-9wfa-3htr")


@pytest.mark.parametrize(
    "text",
    ["", RAW[:-1], RAW + "A", "K7QMX2PD9WFA3HT0", "K7QMX2PD9WFA3HTI", "K7QMX2PD9WFA3HT!"],
)
def test_T_DOM_RECOV_03_well_formed_rejects_wrong_length_or_symbols(text):
    assert CODE_LENGTH == 16
    assert not is_well_formed(text)
