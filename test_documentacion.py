import pytest

from modules.marketplace import documentacion


def test_documentacion_with_energy_extras():
    plan = {
        "habitaciones": [{"nombre": "Salón", "m2": 20}],
        "energy_systems": ["aerotermia", "domotic"],
        "energy_extras_cost": 21000,
        "total_m2": 20
    }
    memoria = documentacion.generar_memoria_constructiva(plan, superficie_finca=100)
    assert "SISTEMAS ENERGÉTICOS SELECCIONADOS" in memoria
    assert "Aerotermia" in memoria
    assert "Domotic" in memoria or "Domótica" in memoria
    assert "Costo asociado: €21,000" in memoria

    presupuesto = documentacion.generar_presupuesto_estimado(plan, coste_m2=1000)
    assert presupuesto["energy_extras_cost"] == 21000
    assert "energy_systems" in presupuesto
    assert "aerotermia" in presupuesto["energy_systems"]
