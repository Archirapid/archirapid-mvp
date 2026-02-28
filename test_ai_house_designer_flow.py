import pytest

from modules.ai_house_designer.flow import _normalize_ai_proposal, PANEL_MIN_M2


def test_normalize_adds_panel_when_missing():
    # no keys at all, but user asked for solar
    prop = {}
    normalized = _normalize_ai_proposal(prop, energy_list=['solar'])
    assert 'paneles_solares' in normalized
    assert normalized['paneles_solares'] == PANEL_MIN_M2


def test_normalize_groups_multiple_keys():
    # proposal has several variants of solar/panel names
    prop = {'solar': 5, 'paneles': 4, 'otro': 10}
    normalized = _normalize_ai_proposal(prop, energy_list=[])
    # should collapse into one entry
    assert 'paneles_solares' in normalized
    assert normalized['paneles_solares'] == 9
    assert 'solar' not in normalized and 'paneles' not in normalized
    assert normalized['otro'] == 10


def test_normalize_preserves_existing_panel():
    # if the proposal already has correct key, it should not change area
    prop = {'paneles_solares': 7}
    normalized = _normalize_ai_proposal(prop, energy_list=['solar'])
    assert normalized['paneles_solares'] == 7


def test_normalize_non_numeric_values():
    # key with non-numeric value should be skipped
    prop = {'paneles': 'muchos', 'salon': 20}
    normalized = _normalize_ai_proposal(prop, energy_list=['solar'])
    # since value not numeric and we asked for solar, should get minimal
    assert normalized['paneles_solares'] == PANEL_MIN_M2
    assert 'salon' in normalized


def test_normalize_removes_non_solar_energy_keys():
    # if the proposal contains terms like aerotermia/geotermia/etc and the
    # user selected those energies, they must not appear as rooms
    prop = {'aerotermia': 5, 'geotermia_extra': 10, 'salon': 20}
    normalized = _normalize_ai_proposal(prop, energy_list=['aerotermia', 'geotermia'])
    assert 'aerotermia' not in normalized
    assert 'geotermia_extra' not in normalized
    # unrelated keys remain
    assert 'salon' in normalized

