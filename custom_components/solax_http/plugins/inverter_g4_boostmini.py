"""SolaX inverter plugin for X1 Boost/Mini G4 devices accessed via HTTP."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)

from ..const import BaseHttpSensorEntityDescription, S16
from ..entity_definitions import X1
from ..plugin_base import plugin_base

SUPPORTED_TYPES = {18, 22}


@dataclass
class InverterSensorDescription(BaseHttpSensorEntityDescription):
    """Sensor description extended with inverter specific metadata."""

    index: int | None = None
    source: str = "Data"  # Data, Info, or Payload
    factor: float = 1.0
    invert_sign: bool = False
    precision: int | None = None


def _resolve_data_value(data: Any, index: int | None) -> Any:
    """Helper to extract a raw value from coordinator data containers."""

    if index is None:
        return None

    containers: list[Any] = []
    if isinstance(data, dict):
        containers.append(data.get("Data"))
        raw_payload = data.get("RawRealtimeData")
        if isinstance(raw_payload, dict):
            containers.append(raw_payload.get("Data"))

    for container in containers:
        if isinstance(container, dict):
            if index in container:
                return container.get(index)
            str_index = str(index)
            if str_index in container:
                return container.get(str_index)
        elif isinstance(container, list) and 0 <= index < len(container):
            return container[index]

    return None


def _make_pv_power_value_function(
    voltage_index: int,
    current_index: int,
    voltage_factor: float,
    current_factor: float,
) -> Callable[[Any, InverterSensorDescription, Any], float | int | None]:
    """Build a value function to derive PV string power from voltage/current."""

    def _value_function(raw_value: Any, descr: InverterSensorDescription, data: Any) -> float | int | None:
        try:
            voltage = float(raw_value) * voltage_factor
        except (TypeError, ValueError):
            return None

        current_raw = _resolve_data_value(data, current_index)
        if current_raw is None:
            return None

        try:
            current = float(current_raw) * current_factor
        except (TypeError, ValueError):
            return None

        return voltage * current

    return _value_function


SENSOR_TYPES = [
    InverterSensorDescription(
        key="ac_power",
        name="AC Power",
        index=6,
        factor=1.0,
        precision=0,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    InverterSensorDescription(
        key="pv1_power",
        name="PV1 Power",
        index=9,
        factor=1.0,
        precision=0,
        value_function=_make_pv_power_value_function(9, 13, 0.1, 0.1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    InverterSensorDescription(
        key="pv2_power",
        name="PV2 Power",
        index=12,
        factor=1.0,
        precision=0,
        value_function=_make_pv_power_value_function(12, 14, 0.1, 0.1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    InverterSensorDescription(
        key="grid_power",
        name="Grid Power",
        index=22,
        factor=1.0,
        precision=0,
        invert_sign=True,
        unit=S16,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    InverterSensorDescription(
        key="today_energy",
        name="Today Energy",
        index=21,
        factor=0.1,
        precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    InverterSensorDescription(
        key="total_energy",
        name="Total Energy",
        index=55,
        factor=0.1,
        precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    InverterSensorDescription(
        key="pv1_voltage",
        name="PV1 Voltage",
        index=9,
        factor=0.1,
        precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    InverterSensorDescription(
        key="pv1_current",
        name="PV1 Current",
        index=13,
        factor=0.1,
        precision=1,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    InverterSensorDescription(
        key="pv2_voltage",
        name="PV2 Voltage",
        index=12,
        factor=0.1,
        precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    InverterSensorDescription(
        key="pv2_current",
        name="PV2 Current",
        index=14,
        factor=0.1,
        precision=1,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    InverterSensorDescription(
        key="inverter_temperature",
        name="Inverter Temperature",
        index=101,
        factor=1.0,
        precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
]


@dataclass
class SolaxInverterG4BoostMiniPlugin(plugin_base):
    """Plugin implementation for X1 Boost/Mini G4 inverters."""

    host: str = ""
    registration: str = ""
    use_x_forwarded_for: bool = True
    initial_payload: dict[str, Any] | None = None
    runtime_type: int | None = None
    device_serial: str | None = None
    info_serial: str | None = None
    firmware: str | None = None
    supports_set_data: bool = False

    _model_name: str | None = None
    _last_payload: dict[str, Any] | None = None

    async def initialize(self, data) -> None:  # type: ignore[override]
        payload = None
        if isinstance(data, dict):
            payload = data.get("RawRealtimeData")
        if payload:
            self._apply_payload(payload)
        elif self.initial_payload:
            self._apply_payload(self.initial_payload)

    @property
    def inverter_model(self) -> str:
        if self._model_name:
            return self._model_name
        if self.runtime_type == 18:
            return "X1 Boost G4"
        if self.runtime_type == 22:
            return "X1 Mini G4"
        return "SolaX Inverter"

    def map_data(self, descr, data) -> Any:  # type: ignore[override]
        if not isinstance(descr, InverterSensorDescription):
            return None
        payload = None
        if isinstance(data, dict):
            payload = data.get("RawRealtimeData")
        if payload:
            self._apply_payload(payload)

        container = None
        if isinstance(data, dict):
            if descr.source.lower() == "data":
                container = data.get("Data")
            elif descr.source.lower() == "info":
                container = data.get("Info")
        if container is None and self._last_payload is not None:
            if descr.source.lower() == "data":
                container = self._last_payload.get("Data")
            elif descr.source.lower() == "info":
                container = self._last_payload.get("Information")

        raw_value = None
        if isinstance(container, dict) and descr.index is not None:
            raw_value = container.get(descr.index)
        elif isinstance(container, list) and descr.index is not None:
            if 0 <= descr.index < len(container):
                raw_value = container[descr.index]

        if raw_value is None:
            return None

        if descr.unit == S16:
            try:
                raw_value_int = int(raw_value)
            except (TypeError, ValueError):
                return None
            if raw_value_int >= 0x8000:
                raw_value_int -= 0x10000
            raw_value = raw_value_int

        if descr.value_function is not None:
            value = descr.value_function(raw_value, descr, data)
            if value is None:
                return None
        else:
            try:
                value = float(raw_value) * descr.factor
            except (TypeError, ValueError):
                return None

        if descr.invert_sign:
            value *= -1

        if descr.precision is not None:
            value = round(value, descr.precision)
        elif isinstance(value, float) and value.is_integer():
            value = int(value)

        return value

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        self._last_payload = payload
        if self.runtime_type is None:
            runtime = payload.get("type")
            try:
                self.runtime_type = int(runtime)
            except (TypeError, ValueError):
                self.runtime_type = None

        if not self.invertertype:
            # All supported runtime types correspond to single-phase (X1) devices.
            self.invertertype = X1

        info = payload.get("Information") or []
        if not self.info_serial and len(info) > 2:
            self.info_serial = str(info[2])
        if self.device_serial is None and payload.get("sn"):
            self.device_serial = str(payload.get("sn"))

        if not self.serialnumber:
            if self.device_serial:
                self.serialnumber = str(self.device_serial)
            elif self.info_serial:
                self.serialnumber = str(self.info_serial)
            elif payload.get("sn"):
                self.serialnumber = str(payload["sn"])
            elif self.registration:
                self.serialnumber = str(self.registration)

        if len(info) > 3 and info[3] not in (None, ""):
            self.hw_version = str(info[3])
        if payload.get("ver"):
            self.sw_version = str(payload["ver"])

        if not self._model_name:
            if self.runtime_type == 18:
                self._model_name = "X1 Boost G4"
            elif self.runtime_type == 22:
                self._model_name = "X1 Mini G4"
            else:
                self._model_name = "SolaX Inverter"


def create_plugin(
    *,
    host: str,
    registration: str,
    use_x_forwarded_for: bool,
    payload: dict[str, Any] | None,
    info_serial: str | None,
    device_serial: str | None,
    firmware: str | None,
) -> SolaxInverterG4BoostMiniPlugin:
    """Factory helper used by PluginFactory to instantiate the plugin."""

    runtime_type = None
    if payload and payload.get("type") is not None:
        try:
            runtime_type = int(payload.get("type"))
        except (TypeError, ValueError):
            runtime_type = None

    plugin = SolaxInverterG4BoostMiniPlugin(
        plugin_name="solax_inverter_g4_boostmini",
        TIME_TYPES=[],
        SENSOR_TYPES=SENSOR_TYPES,
        NUMBER_TYPES=[],
        BUTTON_TYPES=[],
        SELECT_TYPES=[],
        serialnumber=info_serial or device_serial or registration,
        host=host,
        registration=registration,
        use_x_forwarded_for=use_x_forwarded_for,
        initial_payload=payload,
        runtime_type=runtime_type,
        device_serial=device_serial,
        info_serial=info_serial,
        firmware=firmware,
    )
    if firmware:
        plugin.sw_version = firmware
    if info_serial:
        plugin.serialnumber = info_serial
    if payload:
        plugin._apply_payload(payload)
    return plugin
