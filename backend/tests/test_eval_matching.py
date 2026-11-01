"""The eval script's answer matching (decides what counts as top-1 / top-3 correct)."""

from eval.run_eval import make_matches, model_matches


def test_make_matching_handles_case_punctuation_and_aliases() -> None:
    assert make_matches("Mercedes-Benz", "mercedes benz")
    assert make_matches("Volkswagen", "VW")
    assert not make_matches("Ford", "Fiat")


def test_model_matching_is_lenient_about_trims() -> None:
    assert model_matches("MX-5", "MX5 Miata")
    assert model_matches("Golf", "Golf GTI")
    assert not model_matches("Golf", "Polo")
    assert not model_matches("", "Golf")
