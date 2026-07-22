from apps.companies.services.geo_service import cities_match, normalize_city, normalize_state


def test_normalize_city_strips_accents():
    assert normalize_city("São Paulo") == "sao paulo"
    assert normalize_city("  Campinas  ") == "campinas"


def test_cities_match_ignores_case_and_accents():
    assert cities_match("São Paulo", "sao paulo")
    assert not cities_match("São Paulo", "Campinas")


def test_normalize_state():
    assert normalize_state("sp") == "SP"
    assert normalize_state(" Sp ") == "SP"
