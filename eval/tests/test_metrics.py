"""WER-implementáció tesztjei — ez ML-függőség nélkül, ground-truth adat
nélkül is futtatható/ellenőrizhető MOST, mielőtt valós teszt-adat érkezne."""
from __future__ import annotations

import pytest

from eval.metrics import normalize_text, word_error_rate


def test_identical_text_has_zero_wer():
    result = word_error_rate("ez egy teszt mondat", "ez egy teszt mondat")
    assert result.wer == 0.0
    assert result.edit_distance == 0


def test_one_substitution_out_of_four_words():
    result = word_error_rate("ez egy teszt mondat", "ez egy rossz mondat")
    assert result.wer == pytest.approx(1 / 4)
    assert result.edit_distance == 1


def test_one_deletion():
    result = word_error_rate("ez egy teszt mondat", "ez teszt mondat")
    assert result.wer == pytest.approx(1 / 4)


def test_one_insertion():
    result = word_error_rate("ez egy mondat", "ez egy teszt mondat")
    assert result.wer == pytest.approx(1 / 3)


def test_empty_reference_and_empty_hypothesis_is_zero():
    result = word_error_rate("", "")
    assert result.wer == 0.0


def test_empty_reference_nonempty_hypothesis_is_one():
    result = word_error_rate("", "valami")
    assert result.wer == 1.0


def test_normalization_ignores_case_and_punctuation():
    result = word_error_rate("Ez, egy TESZT mondat.", "ez egy teszt mondat")
    assert result.wer == 0.0


def test_normalize_text_collapses_whitespace():
    assert normalize_text("  Szia,   Világ!  ") == "szia világ"


def test_without_normalization_case_difference_counts_as_error():
    result = word_error_rate("Szia Világ", "szia világ", normalize=False)
    assert result.wer > 0.0
