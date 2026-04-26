from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(
    os.environ.get("RUN_DOCKER_INTEGRATION") == "1",
    "Set RUN_DOCKER_INTEGRATION=1 to run Docker integration tests.",
)
@unittest.skipUnless(shutil.which("docker"), "Docker is required for this integration test.")
class DockerPiMqttPiTests(unittest.TestCase):
    compose_file = Path("docker-compose.pi-mqtt-pi.yml")

    @classmethod
    def setUpClass(cls) -> None:
        info = subprocess.run(
            ["docker", "info"],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
        )
        if info.returncode != 0:
            raise unittest.SkipTest(
                "Docker daemon is unavailable. Start Docker Desktop or the Linux engine "
                "before running this integration test."
            )

    def run_compose(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file), *args],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
        )

    def tearDown(self) -> None:
        self.run_compose("down", "--remove-orphans", "-v")

    def test_message_flows_from_ag01_to_bg02_over_broker(self) -> None:
        up = self.run_compose(
            "up",
            "--build",
            "--abort-on-container-exit",
            "--exit-code-from",
            "bg02",
        )

        if up.returncode != 0:
            self.fail(
                "docker integration failed\n"
                f"stdout:\n{up.stdout}\n"
                f"stderr:\n{up.stderr}"
            )

        self.assertIn('"status": "published"', up.stdout)
        self.assertIn('"status": "emitted"', up.stdout)
        self.assertIn('"status": "ready"', up.stdout)
        self.assertIn('"msg_id": "ops-test-0001"', up.stdout)
        self.assertIn('"queue_depth": 1', up.stdout)
        self.assertIn('"queue_depth": 0', up.stdout)
