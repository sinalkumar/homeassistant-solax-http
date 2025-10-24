"""Factory for creating plugin instances for the SolaX HTTP integration."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from typing import Any, Callable

import aiohttp
import async_timeout
from homeassistant.const import CONF_HOST

from .const import (
    CONF_DEVICE_SERIAL,
    CONF_SN,
    CONF_USE_X_FORWARDED_FOR,
    DEFAULT_USE_X_FORWARDED_FOR,
)
from .entity_definitions import (
    BUTTON_TYPES,
    NUMBER_TYPES,
    POW7,
    POW11,
    POW22,
    SELECT_TYPES,
    SENSOR_TYPES,
    TIME_TYPES,
    V10,
    V11,
    V20,
    X1,
    X3,
)
from .plugin_solax_ev_charger import solax_ev_charger_plugin
from .plugin_solax_ev_charger_g2 import solax_ev_charger_plugin_g2
from .plugins.inverter_g4_boostmini import (
    SUPPORTED_TYPES as G4_SUPPORTED_TYPES,
    create_plugin as create_g4_boost_mini_plugin,
)

_LOGGER = logging.getLogger(__name__)

INVERTER_TYPE_FACTORIES: dict[int, Callable[..., Any]] = {}
for inverter_type in G4_SUPPORTED_TYPES:
    INVERTER_TYPE_FACTORIES[inverter_type] = create_g4_boost_mini_plugin


class PluginFactory:
    """Factory class to create plugin instances."""

    @staticmethod
    async def _http_post(
        url: str,
        payload: str,
        retry: int = 3,
        *,
        headers: dict[str, str] | None = None,
        use_x_forwarded_for: bool = True,
    ) -> str | None:
        request_headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if headers:
            request_headers.update(headers)
        if use_x_forwarded_for:
            request_headers.setdefault("X-Forwarded-For", "5.8.8.8")

        try:
            connector = aiohttp.TCPConnector(force_close=True)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with async_timeout.timeout(10):
                    async with session.post(
                        url, data=payload, headers=request_headers
                    ) as resp:
                        if resp.status == 200:
                            return await resp.text()
                        _LOGGER.debug(
                            "Unexpected status code %s for url %s", resp.status, url
                        )
        except (asyncio.TimeoutError, TimeoutError):
            if retry > 0:
                return await PluginFactory._http_post(
                    url,
                    payload,
                    retry=retry - 1,
                    headers=headers,
                    use_x_forwarded_for=use_x_forwarded_for,
                )
            _LOGGER.error("Timeout error reading from Http. Url: %s", url)
        except aiohttp.ServerDisconnectedError:
            if retry > 0:
                return await PluginFactory._http_post(
                    url,
                    payload,
                    retry=retry - 1,
                    headers=headers,
                    use_x_forwarded_for=use_x_forwarded_for,
                )
            _LOGGER.error("Server disconnected error reading from Http. Url: %s", url)
        except aiohttp.client_exceptions.ClientOSError:
            if retry > 0:
                return await PluginFactory._http_post(
                    url,
                    payload,
                    retry=retry - 1,
                    headers=headers,
                    use_x_forwarded_for=use_x_forwarded_for,
                )
            _LOGGER.error("ClientOSError reading from Http. Url: %s", url)
        except aiohttp.ClientError as err:
            if retry > 0:
                return await PluginFactory._http_post(
                    url,
                    payload,
                    retry=retry - 1,
                    headers=headers,
                    use_x_forwarded_for=use_x_forwarded_for,
                )
            _LOGGER.error("ClientError reading from Http. Url: %s", url)
        except Exception as ex:  # pragma: no cover - unexpected errors
            _LOGGER.exception("Error reading from Http. Url: %s", url, exc_info=ex)
        return None

    @staticmethod
    async def _read_runtime_payload(
        host: str, pwd: str, use_x_forwarded_for: bool
    ) -> dict[str, Any] | None:
        text = await PluginFactory._http_post(
            f"http://{host}",
            f"optType=ReadRealTimeData&pwd={pwd}",
            use_x_forwarded_for=use_x_forwarded_for,
        )
        if text is None:
            return None
        if "failed" in text:
            _LOGGER.error("Failed to read data from http: %s", text)
            return None
        try:
            return json.loads(text)
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Failed to decode json: %s", text)
        return None

    @staticmethod
    def _determine_type(sn: str | None) -> int | None:
        if not sn:
            _LOGGER.debug("No serial number available to determine charger type")
            return None

        _LOGGER.info("Trying to determine inverter type from serial %s", sn)
        invertertype = 0
        if sn.startswith("C"):  # G1 EVC
            if len(sn) > 4 and sn[4] == "0":
                invertertype |= V10
            elif len(sn) > 4 and sn[4] == "1":
                invertertype |= V11
            if len(sn) > 1 and sn[1] == "1":
                invertertype |= X1
            elif len(sn) > 1 and sn[1] == "3":
                invertertype |= X3
            if sn[2:4] == "07":
                invertertype |= POW7
            elif sn[2:4] == "11":
                invertertype |= POW11
            elif sn[2:4] == "22":
                invertertype |= POW22
        elif sn.startswith("50"):  # G2 HEC
            invertertype = V20
            if len(sn) > 2 and sn[2] == "3":
                invertertype |= X3
            elif len(sn) > 2 and sn[2] == "2":
                invertertype |= X1
            if len(sn) > 4 and sn[4] == "B":
                invertertype |= POW11
            elif len(sn) > 4 and sn[4] == "M":
                invertertype |= POW22
            elif len(sn) > 4 and sn[4] == "7":
                invertertype |= POW7
        else:
            _LOGGER.debug("Serial %s not recognized as EV charger", sn)
            return None
        return invertertype

    @staticmethod
    async def get_plugin_instance(config: Mapping[str, Any]):
        """Get an instance of plugin based on runtime detection."""

        host = config.get(CONF_HOST)
        pwd = config.get(CONF_SN)
        use_x_forwarded_for = config.get(
            CONF_USE_X_FORWARDED_FOR, DEFAULT_USE_X_FORWARDED_FOR
        )
        device_serial = config.get(CONF_DEVICE_SERIAL)

        if not host or not pwd:
            raise ValueError("Host and registration/password must be provided")

        payload = await PluginFactory._read_runtime_payload(
            host, pwd, use_x_forwarded_for
        )
        if payload is None:
            raise ValueError("Unable to read data from HTTP endpoint")

        information = payload.get("Information") or []
        info_serial = information[2] if len(information) > 2 else None
        firmware = information[4] if len(information) > 4 else None
        if info_serial is not None:
            info_serial = str(info_serial)
        if firmware is not None:
            firmware = str(firmware)

        invertertype = PluginFactory._determine_type(info_serial)
        if invertertype:
            if invertertype & (V10 | V11):
                return solax_ev_charger_plugin(
                    serialnumber=info_serial,
                    invertertype=invertertype,
                    plugin_name="solax_ev_charger",
                    TIME_TYPES=TIME_TYPES,
                    SENSOR_TYPES=SENSOR_TYPES,
                    NUMBER_TYPES=NUMBER_TYPES,
                    BUTTON_TYPES=BUTTON_TYPES,
                    SELECT_TYPES=SELECT_TYPES,
                    sw_version=firmware,
                )
            if invertertype & V20:
                return solax_ev_charger_plugin_g2(
                    serialnumber=info_serial,
                    invertertype=invertertype,
                    plugin_name="solax_ev_charger_g2",
                    TIME_TYPES=TIME_TYPES,
                    SENSOR_TYPES=SENSOR_TYPES,
                    NUMBER_TYPES=NUMBER_TYPES,
                    BUTTON_TYPES=BUTTON_TYPES,
                    SELECT_TYPES=SELECT_TYPES,
                    sw_version=firmware,
                )

        runtime_type_raw = payload.get("type")
        try:
            runtime_type = int(runtime_type_raw)
        except (TypeError, ValueError):
            runtime_type = None

        if runtime_type in INVERTER_TYPE_FACTORIES:
            factory = INVERTER_TYPE_FACTORIES[runtime_type]
            _LOGGER.info("Detected inverter type %s via runtime probe", runtime_type)
            return factory(
                host=host,
                registration=pwd,
                use_x_forwarded_for=use_x_forwarded_for,
                payload=payload,
                info_serial=info_serial,
                device_serial=device_serial,
                firmware=firmware,
            )

        raise ValueError(
            f"Unknown inverter type: serial={info_serial!s} runtime_type={runtime_type_raw!s}"
        )
