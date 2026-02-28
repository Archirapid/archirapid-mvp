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


def test_strip_other_energy_keys():
    # if the proposal includes aerotermia etc these should be removed
    prop = {'aerotermia': 1, 'geotermia': 2, 'salon': 20}
    normalized = _normalize_ai_proposal(prop, energy_list=['aerotermia','geotermia','solar'])
    assert 'aerotermia' not in normalized
    assert 'geotermia' not in normalized
    # solar was in energy_list but there is no solar key so panel minimum added
    assert normalized['paneles_solares'] == PANEL_MIN_M2
    assert normalized['salon'] == 20


def test_total_with_extras_calculation():
    # construct simple design with one room (20 m2 salon) and energy selections
    from modules.ai_house_designer.flow import calculate_total_with_extras, ENERGY_COSTS
    from modules.ai_house_designer.data_model import RoomType, RoomInstance, Plot, HouseDesign

    plot = Plot(id='p', area_m2=100, buildable_ratio=0.3)
    design = HouseDesign(plot)
    rtype = RoomType(code='salon', name='Salón', min_m2=10, max_m2=50, base_cost_per_m2=1000)
    room = RoomInstance(room_type=rtype, area_m2=20)
    design.rooms.append(room)

    # energy flags with aerotermia and domotic selected
    energy_flags = {'aerotermia': True, 'domotic': True}
    # default keep all
    total1 = calculate_total_with_extras(design, energy_flags, keep_energy={})
    # manually compute expected
    base = 20 * 1000
    expected = base + int(20*180) + int(20*150) + ENERGY_COSTS['aerotermia'] + ENERGY_COSTS['domotic']
    assert total1 == expected

    # if user unchecks domotic
    total2 = calculate_total_with_extras(design, energy_flags, keep_energy={'domotic': False})
    assert total2 == expected - ENERGY_COSTS['domotic']
