"""2N Device."""

from json.decoder import JSONDecodeError
import logging

import httpx

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class Hass2NDeviceResponse:
    """API return status."""

    def __init__(self, resp: httpx.Response) -> None:
        """Set it up."""
        self._status_code = resp.status_code
        try:
            self._json = resp.json()
            self._result = self._json.get("result")
        except JSONDecodeError:
            self._status_code = httpx.codes.INTERNAL_SERVER_ERROR


    @property
    def status_code(self) -> int:
        """Return the last status."""
        return self._status_code

    @property
    def json(self) -> dict:
        """Return the json response."""
        return self._json

    @property
    def result(self) -> dict | None:
        """Return the result."""
        return self._result

    @property
    def has_result(self) -> bool:
        """Return true if result is valid."""
        return self._status_code == httpx.codes.OK and self._result is not None

    def result_value(self, key: str) -> str | None:
        """Return value from result or None."""
        if self.has_result:
            return self._result.get(key)
        return None



class Hass2NDevice:  # noqa: D101
    """Device interface."""

    def __init__(
        self, hass: HomeAssistant, host: str, username: str, password: str
    ) -> None:
        """Set up class."""

        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._auth = httpx.DigestAuth(username=username, password=password)
        self._client = httpx.AsyncClient(auth=self._auth, verify=False)
        self._device_name = None
        self._mac_addr = None
        self._device_id = None
        self._online = False
        self._callbacks = set()
        self._system_info: dict | None
        self._log_id = None

    @property
    def device_id(self) -> str:
        """Use the mac."""
        return self._device_id

    @property
    def system_info(self) -> dict:
        """Return device info."""
        return self._system_info

    @property
    def online(self) -> bool:
        """Return status."""
        return self._online

    async def api_get(self, uri: str) -> Hass2NDeviceResponse:
        """Make an API call."""
        url = "https://" + self._host + uri
        resp = httpx.Response(status_code=0)
        try:
            _LOGGER.debug("-> GET %s", url)
            resp = await self._client.get(url)

        except httpx.RemoteProtocolError as exc:
            _LOGGER.error("Error during get: %s", exc)

        _LOGGER.debug("<- Response: code=%d json=%s", resp.status_code, resp.json())
        devresp = Hass2NDeviceResponse(resp)
        self._online = devresp.status_code == httpx.codes.OK
        return devresp

    async def api_call(self, uri: str) -> bool:
        """Make a call and return True if successful."""
        resp = await self.api_get(uri)
        return resp.status_code == httpx.codes.OK

    async def get_system_info(self) -> int:
        """Load initial system info."""
        resp = await self.api_get("/api/system/info")
        if resp.has_result:
            self._system_info = resp.result
            self._device_name = resp.result_value("deviceName")
            self._mac_addr = resp.result_value("macAddr")
            self._device_id = "2N:" + self._mac_addr
        return resp.status_code

    async def get_status(self) -> dict | None:
        """Load the current status."""
        status = {}
        resp = await self.api_get("/api/io/status")
        if resp.has_result:
            status["ports"] = resp.result_value("ports")

        resp = await self.api_get("/api/switch/status")
        if resp.has_result:
            status["switches"] = resp.result_value("switches")

        if self._log_id is None:
            resp = await self.api_get("/api/log/subscribe")
            self._log_id = resp.result_value("id")
        if self._log_id is not None:
            resp = await self.api_get(f"/api/log/pull?id={self._log_id}")
            status["events"] = resp.result_value("events")
        return status

    def register_callback(self, callback) -> None:
        """Register callback, called when device changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)
