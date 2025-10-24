"""SolaX inverter plugin for X1 Boost/Mini G4 devices accessed via HTTP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

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


def _extract_index_value(container: Any, index: int | None) -> Any:
    """Return the raw value stored at *index* from *container*."""

    if index is None or container is None:
        return None

    if isinstance(container, dict):
        if index in container:
            return container.get(index)
        str_index = str(index)
        if str_index in container:
            return container.get(str_index)
        return None

    if isinstance(container, list) and 0 <= index < len(container):
        return container[index]

    return None


def _get_container_for_source(source: Any, container_type: str) -> Any:
    """Return the first matching container for the requested source type."""

    if source is None:
        return None

    containers: list[dict[str, Any] | list[Any]] = []

    if isinstance(source, dict):
        raw_payload = source.get("RawRealtimeData")
        if isinstance(raw_payload, dict):
            containers.append(raw_payload)
        containers.append(source)
    elif isinstance(source, list):
        containers.append(source)

    for candidate in containers:
        if not isinstance(candidate, (dict, list)):
            continue
        if isinstance(candidate, list):
            return candidate

        match container_type.lower():
            case "data":
                container = candidate.get("Data")
            case "info" | "information":
                container = candidate.get("Information") or candidate.get("Info")
            case "payload":
                container = candidate
            case _:
                container = None

        if container is not None:
            return container

    return None


def _resolve_data_value(
    data: Any,
    last_payload: dict[str, Any] | None,
    index: int | None,
    source: str = "Data",
) -> Any:
    """Resolve the raw value for *index* from the available payloads."""

    for container_source in (data, last_payload):
        container = _get_container_for_source(container_source, source)
        raw_value = _extract_index_value(container, index)
        if raw_value is not None:
            return raw_value

    return None


def _make_pv_power_function(
    current_index: int,
    current_factor: float,
) -> Callable[[float, InverterSensorDescription, Any, dict[str, Any] | None], float | None]:
    """Create a value function that derives PV power from voltage and current."""

    def _value_function(
        voltage: float,
        descr: InverterSensorDescription,
        data: Any,
        last_payload: dict[str, Any] | None,
    ) -> float | None:
        raw_current = _resolve_data_value(data, last_payload, current_index)
        if raw_current is None:
            return None

        try:
            current = float(raw_current) * current_factor
        except (TypeError, ValueError):
            return None

        return voltage * current

    return _value_function


SENSOR_TYPES = [
    InverterSensorDescription(
        key="ac_power",
        name="AC Power",
        index=3,
        factor=1.0,
        precision=0,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    InverterSensorDescription(
        key="pv1_power",
        name="PV1 Power",
        index=0,
        factor=0.1,
        precision=0,
        value_function=_make_pv_power_function(1, 0.1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    InverterSensorDescription(
        key="pv2_power",
        name="PV2 Power",
        index=13,
        factor=0.1,
        precision=0,
        value_function=_make_pv_power_function(10, 0.1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    InverterSensorDescription(
        key="grid_power",
        name="Grid Power",
        index=72,
        factor=1.0,
        precision=0,
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
        index=74,
        factor=0.1,
        precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    InverterSensorDescription(
        key="pv1_voltage",
        name="PV1 Voltage",
        index=0,
        factor=0.1,
        precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    InverterSensorDescription(
        key="pv1_current",
        name="PV1 Current",
        index=1,
        factor=0.1,
        precision=1,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    InverterSensorDescription(
        key="pv2_voltage",
        name="PV2 Voltage",
        index=13,
        factor=0.1,
        precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    InverterSensorDescription(
        key="pv2_current",
        name="PV2 Current",
        index=10,
        factor=0.1,
        precision=1,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    InverterSensorDescription(
        key="inverter_temperature",
        name="Inverter Temperature",
        index=23,
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
            if not isinstance(payload, dict):
                payload = data
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
        if isinstance(data, dict):
            payload = data.get("RawRealtimeData")
            if not isinstance(payload, dict):
                payload = data
            if isinstance(payload, dict):
                self._apply_payload(payload)

        container = _get_container_for_source(data, descr.source)
        if container is None:
            container = _get_container_for_source(self._last_payload, descr.source)

        raw_value = _extract_index_value(container, descr.index)
        if raw_value is None:
            return None

        if descr.unit == S16:
            try:
                raw_int = int(raw_value)
            except (TypeError, ValueError):
                return None
            if raw_int >= 0x8000:
                raw_int -= 0x10000
            raw_value = raw_int

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None

        value *= descr.factor

        if descr.value_function is not None:
            value = descr.value_function(value, descr, data, self._last_payload)
            if value is None:
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
