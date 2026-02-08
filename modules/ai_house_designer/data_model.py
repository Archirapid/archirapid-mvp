from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class Plot:
    id: str
    area_m2: float  # superficie total de la parcela
    buildable_ratio: float  # por ejemplo 0.33
    shape: str = "rectangular"  # o "L", etc.
    orientation: Optional[str] = None  # norte, sur, etc.

    @property
    def max_buildable_m2(self) -> float:
        return self.area_m2 * self.buildable_ratio


@dataclass
class RoomType:
    code: str  # p.ej. "bedroom_master"
    name: str
    min_m2: float
    max_m2: float
    default_height: float = 2.7
    requires_window: bool = True
    requires_exterior_wall: bool = False
    can_be_upstairs: bool = True
    base_cost_per_m2: float = 0.0
    extra_cost_factors: Dict[str, float] = field(default_factory=dict)


@dataclass
class RoomInstance:
    room_type: RoomType
    area_m2: float
    floor: int = 0
    tags: List[str] = field(default_factory=list)


@dataclass
class HouseDesign:
    plot: Plot
    rooms: List[RoomInstance] = field(default_factory=list)
    style: Optional[str] = None
    materials: List[str] = field(default_factory=list)
    budget_limit: Optional[float] = None

    def total_area(self) -> float:
        return sum(room.area_m2 for room in self.rooms)

    def estimated_cost(self) -> float:
        total_cost = 0.0
        for room in self.rooms:
            # Base cost
            total_cost += room.area_m2 * room.room_type.base_cost_per_m2
            # Extra cost factors
            for factor_name, factor_value in room.room_type.extra_cost_factors.items():
                total_cost += room.area_m2 * factor_value
        return total_cost


def create_example_design() -> HouseDesign:
    # Plot ficticio de 500 m² al 33%
    plot = Plot(
        id="example_plot_001",
        area_m2=500.0,
        buildable_ratio=0.33,
        shape="rectangular",
        orientation="sur"
    )

    # Tres RoomType
    bedroom_master_type = RoomType(
        code="bedroom_master",
        name="Dormitorio Principal",
        min_m2=12.0,
        max_m2=25.0,
        default_height=2.7,
        requires_window=True,
        requires_exterior_wall=True,
        can_be_upstairs=True,
        base_cost_per_m2=800.0,
        extra_cost_factors={"premium_finish": 200.0}
    )

    bedroom_type = RoomType(
        code="bedroom",
        name="Dormitorio",
        min_m2=8.0,
        max_m2=15.0,
        default_height=2.7,
        requires_window=True,
        requires_exterior_wall=False,
        can_be_upstairs=True,
        base_cost_per_m2=600.0
    )

    living_kitchen_type = RoomType(
        code="living_kitchen",
        name="Salón-Cocina",
        min_m2=25.0,
        max_m2=50.0,
        default_height=2.7,
        requires_window=True,
        requires_exterior_wall=True,
        can_be_upstairs=False,
        base_cost_per_m2=700.0,
        extra_cost_factors={"kitchen_equipment": 300.0}
    )

    # Tres rooms que sumen menos de 165 m²
    rooms = [
        RoomInstance(
            room_type=bedroom_master_type,
            area_m2=18.0,
            floor=0,
            tags=["principal", "suite"]
        ),
        RoomInstance(
            room_type=bedroom_type,
            area_m2=12.0,
            floor=0,
            tags=["children"]
        ),
        RoomInstance(
            room_type=living_kitchen_type,
            area_m2=35.0,
            floor=0,
            tags=["open_plan", "social"]
        )
    ]

    # HouseDesign
    design = HouseDesign(
        plot=plot,
        rooms=rooms,
        style="moderno",
        materials=["brick", "concrete", "glass"],
        budget_limit=150000.0
    )

    return design