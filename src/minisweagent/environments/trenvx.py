import asyncio
import logging
from typing import Any

from sandbox_sdk import Sandbox

from minisweagent.environments.trenv_config import *


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
        self._build_template()
        self._setup_container()

    def _build_template(self):
        self.logger.info(f"Building the template {self.config.template_id} using the template-manager")
        config = load_trenvx_template()
        if not self.config.always_rebuild and template_exists_and_matches(config["data_root"], self.config):
            self.logger.info("Skipping rebuild!")
            return
        config = add_trenvx_template(
            config=config,
            template_id=self.config.template_id,
            docker_img=self.config.image,
            vcpu=self.config.vcpu,
            mem_mb=self.config.mem_mb,
            disk_mb=self.config.disk_mb,
            vmm_type=self.config.vmm_type,
            kernel_version=self.config.kernel_version,
            no_pull=self.config.no_pull,
            huge_pages=self.config.huge_pages,
            overlay=self.config.overlay,
            start_cmd=self.config.start_cmd,
        )
        config = change_target_template(config=config, template_id=self.config.template_id)
        build_template(config, self.config.template_id)
        self.logger.info(f"Built the template {self.config.template_id}")

    def _setup_container(self):
        self.logger.info(f"Setting up Trenvx sandbox with template {self.config.template_id}")
        self.ci = self._ev_loop.run_until_complete(
            Sandbox.create(
                template=self.config.template_id,
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
        if not hasattr(self, "_ev_loop"):
            return
        if not hasattr(self, "ci"):
            return
        self._ev_loop.run_until_complete(self.ci.close())
        self._ev_loop.close()

    def __del__(self):
        # Prevent double close from Python's GC
        if hasattr(self, "_ev_loop") and not self._ev_loop.is_closed():
            self.cleanup()
