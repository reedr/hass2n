"""2N Device."""

import logging

import httpx

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class Hass2NDeviceResponse:
    """API return status."""

    def __init__(self, resp: httpx.Response) -> None:
        """Set it up."""
        self._status_code = resp.status_code
        self._json = resp.json()

    @property
    def status_code(self) -> int:
        """Return the last status."""
        return self._status_code

    @property
    def json(self) -> dict:
        """Return the json response."""
        return self._json


class Hass2NDevice:  # noqa: D101
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
        self._deviceName = None
        self._macAddr = None
        self._deviceId = None
        self._online = False
        self._callbacks = set()
        self._system_info: dict | None

    @property
    def device_id(self) -> str:
        """Use the mac."""
        return self._deviceId

    @property
    def system_info(self) -> dict:
        """Return device info."""
        return self._system_info

    @property
    def status(self) -> dict:
        """Return last status."""
        return self._status

    @property
    def online(self) -> bool:
        """Return status."""
        return self._online

    async def api_get(self, uri: str) -> Hass2NDeviceResponse:
        """Make an API call."""
        url = "https://" + self._host + uri
        resp = await self._client.get(url)
        _LOGGER.error(f"{url} -> {resp.status_code}")  # noqa: G004
        devresp = Hass2NDeviceResponse(resp)
        self._online = (devresp.status_code == httpx.codes.OK)
        return devresp

    async def api_call(self, uri: str) -> bool:
        """Make a call and return True if successful."""
        resp = await self.api_get(uri)
        return resp.status_code == httpx.codes.OK

    async def get_system_info(self) -> int:
        """Load initial system info."""
        resp = await self.api_get("/api/system/info")
        if resp.status_code == httpx.codes.OK:
            info = resp.json["result"]
            self._system_info = info
            self._deviceName = info["deviceName"]
            self._macAddr = info["macAddr"]
            self._deviceId = "2N:" + self._macAddr
        return resp.status_code

    async def get_status(self) -> dict | None:
        """Load the current status."""
        status = {}
        resp = await self.api_get("/api/io/status")
        if resp.status_code != httpx.codes.OK:
            return None
        status["ports"] = resp.json["result"]["ports"]

        resp = await self.api_get("/api/switch/status")
        if resp.status_code != httpx.codes.OK:
            return None
        status["switches"] = resp.json["result"]["switches"]
        return status

    def register_callback(self, callback) -> None:
        """Register callback, called when device changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)
