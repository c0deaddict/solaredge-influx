from pydantic import BaseModel, PrivateAttr
from typing import Optional

class SolaredgeConfig(BaseModel):
    site_id: str
    serial: str
    api_key_file: str
    _api_key: Optional[str] = PrivateAttr(default_factory=lambda: None)

    @property
    def api_key(self):
        if self._api_key is None:
            with open(self.api_key_file, "r") as f:
                self._api_key = f.read().strip()
        return self._api_key


class InfluxDBConfig(BaseModel):
    url: str
    token_file: str
    org: str
    bucket: str
    _token: Optional[str] = PrivateAttr(default_factory=lambda: None)

    @property
    def token(self):
        if self._token is None:
            with open(self.token_file, "r") as f:
                self._token = f.read().strip()
        return self._token


class Config(BaseModel):
    solaredge: SolaredgeConfig
    influxdb: InfluxDBConfig


