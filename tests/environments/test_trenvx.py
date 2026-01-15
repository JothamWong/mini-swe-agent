import os
import subprocess
from unittest.mock import patch

import pytest

from minisweagent.environments.trenvx import TrenvxEnvironmentConfig, TrenvxEnvironment


@pytest.mark.slow
def test_trenvx_basic_execution():
    # envConfig = TrenvxEnvironmentConfig(template="default-fc", target_addr="127.0.0.1")
    env = TrenvxEnvironment(template="default-fc", target_addr="127.0.0.1")
    try:
        result = env.execute("python -c \"print('Hello World')\"")
        assert result["returncode"] == 0
        assert "Hello World" in result["output"]
    finally:
        env.cleanup()
