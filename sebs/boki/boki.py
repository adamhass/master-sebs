from typing import cast, Dict, List, Optional, Type, Tuple

import docker

from sebs.cache import Cache
from sebs.config import SeBSConfig
from sebs.storage.resources import SelfHostedSystemResources
from sebs.utils import LoggingHandlers
from sebs.boki.config import BokiConfig
from sebs.boki.function import BokiFunction, HTTPTrigger
from sebs.faas.function import Function, FunctionConfig, ExecutionResult, Trigger
from sebs.faas.system import System
from sebs.faas.config import Resources
from sebs.benchmark import Benchmark


class Boki(System):
    """
    Boki provider for SeBS.

    Boki functions are pre-deployed Go binaries running inside Docker Compose
    on a single EC2 instance. This provider is a thin wrapper that invokes
    functions via the Boki HTTP gateway — it does NOT manage Boki's lifecycle.
    """

    @staticmethod
    def name():
        return "boki"

    @staticmethod
    def typename():
        return "Boki"

    @staticmethod
    def function_type() -> "Type[Function]":
        return BokiFunction

    @property
    def config(self) -> BokiConfig:
        return self._config

    def __init__(
        self,
        sebs_config: SeBSConfig,
        config: BokiConfig,
        cache_client: Cache,
        docker_client: docker.client,
        logger_handlers: LoggingHandlers,
    ):
        super().__init__(
            sebs_config,
            cache_client,
            docker_client,
            SelfHostedSystemResources(
                "boki", config, cache_client, docker_client, logger_handlers
            ),
        )
        self.logging_handlers = logger_handlers
        self._config = config

    def shutdown(self):
        super().shutdown()

    # -- Boki functions are pre-deployed: packaging and deployment are no-ops --

    def package_code(
        self,
        directory: str,
        language_name: str,
        language_version: str,
        architecture: str,
        benchmark: str,
        is_cached: bool,
        container_deployment: bool,
    ) -> Tuple[str, int, str]:
        return directory, 0, ""

    def create_function(
        self,
        code_package: Benchmark,
        func_name: str,
        container_deployment: bool,
        container_uri: str,
    ) -> "BokiFunction":
        function_cfg = FunctionConfig.from_benchmark(code_package)
        return BokiFunction(
            self._config.gateway_url,
            self._config.function_name,
            code_package.benchmark,
            code_package.hash,
            function_cfg,
        )

    def cached_function(self, function: Function):
        pass

    def update_function(
        self,
        function: Function,
        code_package: Benchmark,
        container_deployment: bool,
        container_uri: str,
    ):
        pass

    def update_function_configuration(self, function: Function, code_package: Benchmark):
        pass

    def create_trigger(self, func: Function, trigger_type: Trigger.TriggerType) -> Trigger:
        function = cast(BokiFunction, func)
        if trigger_type != Trigger.TriggerType.HTTP:
            raise RuntimeError("Boki only supports HTTP triggers")

        trigger = HTTPTrigger(function.url)
        trigger.logging_handlers = self.logging_handlers
        function.add_trigger(trigger)
        return trigger

    def download_metrics(
        self,
        function_name: str,
        start_time: int,
        end_time: int,
        requests: Dict[str, ExecutionResult],
        metrics: dict,
    ):
        pass

    def enforce_cold_start(self, functions: List[Function], code_package: Benchmark):
        raise NotImplementedError(
            "Boki cold start requires restarting Docker containers. "
            "Use the restart script manually."
        )

    @staticmethod
    def default_function_name(
        code_package: Benchmark, resources: Optional[Resources] = None
    ) -> str:
        return "boki-{}-{}".format(
            code_package.benchmark,
            code_package.language_name,
        )

    def get_function(self, code_package: Benchmark, func_name: Optional[str] = None) -> Function:
        """
        Override to skip the entire code packaging/building pipeline.
        Boki functions are pre-deployed Go binaries — SeBS never builds them.
        """
        if not func_name:
            func_name = self.default_function_name(code_package)

        # Check cache for existing function
        functions = code_package.functions
        if functions and func_name in functions:
            try:
                function = self.function_type().deserialize(functions[func_name])
                self.cached_function(function)
                self.logging.info(f"Using cached Boki function: {func_name}")
                return function
            except RuntimeError:
                self.logging.warning(f"Cached function {func_name} not available, recreating")

        # Create new function (just a pointer to the gateway).
        # Skip cache — no code package was built, so cache has no config.json.
        self.logging.info(
            f"Creating Boki function {func_name} -> {self._config.gateway_url}"
        )
        function = self.create_function(code_package, func_name, False, "")
        return function
