import shutil
import subprocess

import pytest


@pytest.mark.e2e
def test_docker_compose_happy_path():
    if shutil.which("docker") is None:
        pytest.skip("docker is not installed")

    cmd = ["docker", "compose", "-f", "docker/docker-compose.yml", "config"]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
