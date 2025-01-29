from dataclasses import dataclass
from datetime import date


@dataclass
class EnergyStatisticsDTO:
    datefield: date
    consumed_energy: int
    delivered_heat: int
    delivered_cooling: int
