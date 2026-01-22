import os
import tomlkit
from tomlkit.items import SingleKey, KeyType
import sys
from typing import Optional
from pathlib import Path
import subprocess
from pydantic import BaseModel

DEFAULT_TRENV_CONFIG_FILENAME = "example_config.toml"
DEFAULT_TRENV_TEMPLATE_MANAGER_BINARY = ""


class TrenvxEnvironmentConfig(BaseModel):
    """
    Config for Trenvx Sandbox's create function parameters
    NOTE: The API for the creation of sandbox does include hooks as well.
    """

    # Meta parameters
    always_rebuild: bool = False
    # Parameters for the creation of the template
    image: str
    """Docker image to pull"""
    template_id: str
    """Trenvx template id name."""
    vcpu: int = 1
    mem_mb: int = 2048
    disk_mb: int = 4096
    vmm_type: str = "firecracker"
    kernel_version: str = "fc-6.1.134"
    no_pull: bool = False
    huge_pages: bool = False
    overlay: bool = True
    start_cmd: dict[str, str] | None = None
    # Parameters for the creation of the sandbox
    cwd: str | None = None
    """Current working directory to use"""
    target_addr: str = "127.0.0.1"
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


def __get_default_trenv_config_path():
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[3]
    config_path = (
        project_root
        / "src"
        / "minisweagent"
        / "environments"
        / DEFAULT_TRENV_CONFIG_FILENAME
    )
    if not config_path.exists():
        raise ValueError(f"config file not found at {config_path}")
    return config_path


def __get_template_manager_binary_path():
    current_file = Path(__file__).resolve()
    # environments -> minisweagent -> src -> mini-swe-agent
    project_root = current_file.parents[3]
    binary_path = (
        project_root
        / "trenv-x"
        / "packages"
        / "template-manager"
        / "bin"
        / "template-manager"
    )
    if not binary_path.exists():
        raise ValueError(f"template-manager binary not found at {binary_path}")
    return binary_path


def template_exists_and_matches(
    data_root: str,
    config: TrenvxEnvironmentConfig,
) -> bool:
    template_file = Path(data_root) / "templates" / config.template_id / "template.toml"
    if not template_file.exists():
        return False

    with open(template_file, "rb") as f:
        existing = tomlkit.load(f)

    checks = [
        (config.image, existing.get("docker_img")),
        (config.vcpu, existing.get("vcpu")),
        (config.mem_mb, existing.get("mem_mb")),
        (config.disk_mb, existing.get("disk_mb")),
        (config.vmm_type, existing.get("vmm_type")),
        (config.kernel_version, existing.get("kernel_version")),
        (config.overlay, existing.get("overlay")),
    ]

    return all(expected == actual for expected, actual in checks)


def build_template(config: tomlkit.TOMLDocument, template_id: str):
    config_path = Path(f"{template_id}.toml").resolve()
    with open(str(config_path), "w", encoding="utf-8") as outf:
        outf.write(tomlkit.dumps(config))
    tmgr_bin_path = __get_template_manager_binary_path().resolve()
    working_dir = tmgr_bin_path.parent.parent
    command = [
        str(tmgr_bin_path),
        "--config",
        str(config_path),
    ]
    try:
        subprocess.run(
            command,
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to build the template: {e.returncode}")
        print(e.stderr)
        raise


def load_trenvx_template(file_path: str | None = None) -> tomlkit.TOMLDocument:
    if file_path is None or not Path(file_path).exists():
        file_path = __get_default_trenv_config_path()
    with open(file_path, "rb") as f:
        return tomlkit.load(f)


def add_trenvx_template(
    config: tomlkit.TOMLDocument,
    template_id: str,
    docker_img: str,
    vcpu: int,
    mem_mb: int,
    disk_mb: int,
    vmm_type: str = "firecracker",
    kernel_version: str = "fc-6.1.134",
    no_pull: bool = False,
    huge_pages: bool = False,
    overlay: bool = True,
    start_cmd: dict[str, str] | None = None,
) -> tomlkit.TOMLDocument:
    new_template = tomlkit.table()
    new_template["vcpu"] = vcpu
    new_template["mem_mb"] = mem_mb
    new_template["disk_mb"] = disk_mb
    new_template["docker_img"] = docker_img
    new_template["vmm_type"] = vmm_type
    new_template["kernel_version"] = kernel_version
    new_template["no_pull"] = no_pull
    new_template["huge_pages"] = huge_pages
    new_template["overlay"] = overlay
    if start_cmd is not None:
        cmd_table = tomlkit.table()
        for k, v in start_cmd.items():
            if v is not None:
                cmd_table[k] = v
        new_template["start_cmd"] = cmd_table
    # Use SingleKey with KeyType.Basic to force quotes around the template_id
    quoted_key = SingleKey(template_id, t=KeyType.Basic)
    config["template"][quoted_key] = new_template
    return config


def change_target_template(
    config: tomlkit.TOMLDocument, template_id: str
) -> tomlkit.TOMLDocument:
    if "template" in config and template_id not in config["template"]:
        raise ValueError(
            f"Template {template_id} has not been added to the configuration file"
        )
    if "template_manager" not in config:
        raise ValueError("template is missing the [template_manager] table")
    config["template_manager"]["template_id"] = template_id
    return config
