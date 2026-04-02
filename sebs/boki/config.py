from typing import cast, Optional

from sebs.cache import Cache
from sebs.faas.config import Config, Credentials, Resources
from sebs.storage.resources import SelfHostedResources
from sebs.storage.config import NoSQLStorageConfig, PersistentStorageConfig
from sebs.utils import LoggingHandlers


class BokiCredentials(Credentials):
    def serialize(self) -> dict:
        return {}

    @staticmethod
    def deserialize(config: dict, cache: Cache, handlers: LoggingHandlers) -> Credentials:
        return BokiCredentials()


class BokiResources(SelfHostedResources):
    def __init__(
        self,
        storage_cfg: Optional[PersistentStorageConfig] = None,
        nosql_storage_cfg: Optional[NoSQLStorageConfig] = None,
    ):
        super().__init__("boki", storage_cfg, nosql_storage_cfg)

    def serialize(self) -> dict:
        return super().serialize()

    @staticmethod
    def initialize(res: Resources, config: dict):
        pass

    def update_cache(self, cache: Cache):
        super().update_cache(cache)

    @staticmethod
    def deserialize(config: dict, cache: Cache, handlers: LoggingHandlers) -> Resources:
        ret = BokiResources()
        ret._resources_id = "boki-predeployed"
        ret.logging_handlers = handlers
        return ret


class BokiConfig(Config):
    def __init__(self, gateway_url: str = "", function_name: str = "statefulBench"):
        super().__init__(name="boki")
        self._credentials = BokiCredentials()
        self._resources = BokiResources()
        self._gateway_url = gateway_url
        self._function_name = function_name

    @staticmethod
    def typename() -> str:
        return "Boki.Config"

    @staticmethod
    def initialize(cfg: Config, dct: dict):
        pass

    @property
    def credentials(self) -> BokiCredentials:
        return self._credentials

    @property
    def resources(self) -> BokiResources:
        return self._resources

    @resources.setter
    def resources(self, val: BokiResources):
        self._resources = val

    @property
    def gateway_url(self) -> str:
        return self._gateway_url

    @property
    def function_name(self) -> str:
        return self._function_name

    @staticmethod
    def deserialize(config: dict, cache: Cache, handlers: LoggingHandlers) -> Config:
        gateway_url = config.get("gateway_url", "")
        function_name = config.get("function_name", "statefulBench")
        config_obj = BokiConfig(gateway_url=gateway_url, function_name=function_name)
        config_obj.logging_handlers = handlers
        return config_obj

    def serialize(self) -> dict:
        return {
            "name": "boki",
            "region": self._region,
            "gateway_url": self._gateway_url,
            "function_name": self._function_name,
        }

    def update_cache(self, cache: Cache):
        self.resources.update_cache(cache)
