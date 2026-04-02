import concurrent.futures
from typing import Optional

from sebs.faas.function import ExecutionResult, Function, FunctionConfig, Trigger


class HTTPTrigger(Trigger):
    def __init__(self, url: str):
        super().__init__()
        self.url = url

    @staticmethod
    def typename() -> str:
        return "Boki.HTTPTrigger"

    @staticmethod
    def trigger_type() -> Trigger.TriggerType:
        return Trigger.TriggerType.HTTP

    def sync_invoke(self, payload: dict) -> ExecutionResult:
        self.logging.debug(f"Invoke Boki function at {self.url}")
        return self._http_invoke(payload, self.url, verify_ssl=False)

    def async_invoke(self, payload: dict) -> concurrent.futures.Future:
        pool = concurrent.futures.ThreadPoolExecutor()
        fut = pool.submit(self.sync_invoke, payload)
        return fut

    def serialize(self) -> dict:
        return {"type": "HTTP", "url": self.url}

    @staticmethod
    def deserialize(obj: dict) -> Trigger:
        return HTTPTrigger(obj["url"])


class BokiFunction(Function):
    def __init__(
        self,
        gateway_url: str,
        function_name: str,
        benchmark: str,
        code_package_hash: str,
        config: FunctionConfig,
    ):
        super().__init__(benchmark, function_name, code_package_hash, config)
        self._gateway_url = gateway_url
        self._function_name = function_name
        self._url = f"{gateway_url}/function/{function_name}"

    @property
    def url(self) -> str:
        return self._url

    @property
    def gateway_url(self) -> str:
        return self._gateway_url

    @staticmethod
    def typename() -> str:
        return "Boki.BokiFunction"

    def serialize(self) -> dict:
        return {
            **super().serialize(),
            "gateway_url": self._gateway_url,
            "function_name": self._function_name,
            "url": self._url,
        }

    @staticmethod
    def deserialize(cached_config: dict) -> "BokiFunction":
        cfg = FunctionConfig.deserialize(cached_config["config"])
        return BokiFunction(
            cached_config["gateway_url"],
            cached_config["function_name"],
            cached_config["benchmark"],
            cached_config["hash"],
            cfg,
        )

    def stop(self):
        pass
