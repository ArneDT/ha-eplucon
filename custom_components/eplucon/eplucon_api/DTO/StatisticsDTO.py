from dataclasses import dataclass
from typing import Optional


@dataclass
class StatisticsDTO:
    heating_supply_setpoint: Optional[float] = None
    cooling_supply_setpoint: Optional[float] = None
    zone_dg1_temperature: Optional[float] = None
    zone_sg2_temperature: Optional[float] = None
    zone_sg3_temperature: Optional[float] = None
    zone_sg4_temperature: Optional[float] = None
    heating_setpoint_dg1: Optional[float] = None
    heating_setpoint_sg2: Optional[float] = None
    heating_setpoint_sg3: Optional[float] = None
    heating_setpoint_sg4: Optional[float] = None
    cooling_setpoint_dg1: Optional[float] = None
    cooling_setpoint_sg2: Optional[float] = None
    cooling_setpoint_sg3: Optional[float] = None
    cooling_setpoint_sg4: Optional[float] = None
    valve_position_sg2: Optional[float] = None
    valve_position_sg3: Optional[float] = None
    valve_position_sg4: Optional[float] = None
