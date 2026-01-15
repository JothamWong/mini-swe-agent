import asyncio
import logging
from typing import Any

from pydantic import BaseModel
from sandbox_sdk import Sandbox


class TrenvxEnvironmentConfig(BaseModel):
    """
    Config for Trenvx Sandbox's create function parameters
    NOTE: The API for the creation of sandbox does include hooks as well.
    """

    template: str
    """Trenvx template."""
    cwd: str | None = None
    """Current working directory to use"""
    target_addr: str
    """IP address of where the trenvx backend is running."""
    env: dict[str, str] = {}
    """Environment variables to forward to container"""
    timeout: float = 60
    """Timeout for sandbox to initialize in seconds"""
    metadata: dict[str, str] = {}
    """Dictionary of strings that is stored alongside the running sandbox. Can be seen when one lists running sandboxes."""
    connect_rpc: bool = True
    """Whether connect rpc (SandboxRpc) or not"""
    enable_diff_snapshot: bool = False
    """Whether enable diff snapshot on sandbox"""


class TrenvxEnvironment:
    """
    Executes bash commands in a Trenvx sandbox
    https://github.com/kvcache-ai/TrEnv-X.git.

    NOTE:
    - templates passed in must currently be manually created using trenvx's
      template manager binary (Refer to the README.md in the subfolder).
    - The TrenvX backend is assumed to be running at the specified target_addr.

    TODO: Actually allow passing in a toml config file for the template, but
    the config logic for mini-swe-agent seems needlessly complex so it takes a bit
    to figure out...
    """

    def __init__(self, *, config_class: type = TrenvxEnvironmentConfig, logger: logging.Logger | None = None, **kwargs):
        self.logger = logger or logging.getLogger("minisweagent.environment")
        self.config = config_class(**kwargs)
        self._ev_loop = asyncio.new_event_loop()
        self._setup_container()

    def _setup_container(self):
        # TODO: In the future actually make the template too?
        self.logger.info(f"Setting up Trenvx sandbox with template {self.config.template}")
        self.ci = self._ev_loop.run_until_complete(
            Sandbox.create(
                template=self.config.template,
                cwd=self.config.cwd,
                target_addr=self.config.target_addr,
                env_vars=self.config.env,
                timeout=self.config.timeout,
                metadata=self.config.metadata,
                connect_rpc=self.config.connect_rpc,
                enable_diff_snapshot=self.config.enable_diff_snapshot,
            )
        )
        self.logger.info("Successfully set up Trenv sandbox")

    def get_template_vars(self) -> dict[str, Any]:
        return self.config.model_dump()

    def execute(self, command: str, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        self.logger.info(f"Executing {command=} in {cwd=} with {timeout=}")
        result = self._ev_loop.run_until_complete(
            self.ci.process.start_and_wait(
                cmd=command,
                env_vars=self.config.env,
                cwd=self.config.cwd,
                timeout=self.config.timeout,
            )
        )

        return {"output": result.stdout, "returncode": result.exit_code}

    def cleanup(self):
        self.logger.info("Cleaning up")
        self._ev_loop.run_until_complete(self.ci.close())
        self._ev_loop.close()
        self.logger.info("Cleaned up trenvx and evloop successfully")

    def __del__(self):
        # Prevent double close from Python's GC
        if not self._ev_loop.is_closed():
            self.cleanup()
