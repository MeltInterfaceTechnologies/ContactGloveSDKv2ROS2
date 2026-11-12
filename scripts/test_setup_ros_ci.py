"""Run the real setup helper with recording commands, without root or network."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/setup_ros_ci.sh"
STUB = '''#!{python}
import json, os, pathlib, sys
command = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
record = [command, *args]
if command == "sha256sum":
    record.append(sys.stdin.read())
with open(os.environ["COMMAND_LOG"], "a") as log:
    log.write(json.dumps(record) + "\\n")
if command == "lsb_release":
    print(os.environ["TEST_OS"] if args == ["-is"] else os.environ["TEST_CODENAME"])
elif command == "dpkg":
    assert args == ["--print-architecture"], args
    print(os.environ["TEST_ARCH"])
elif command == "curl":
    pathlib.Path(args[args.index("--output") + 1]).write_bytes(b"test package")
if os.environ.get("FAIL_COMMAND") == command:
    sys.exit(1)
if command == "sudo" and os.environ.get("FAIL_SUDO") in args:
    sys.exit(1)
'''


class SetupRosCiTests(unittest.TestCase):
    def run_setup(self, distro="humble", codename="jammy", **overrides):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            bindir = directory / "bin"
            bindir.mkdir()
            for command in ("sudo", "lsb_release", "dpkg", "curl", "sha256sum"):
                stub = bindir / command
                stub.write_text(STUB.format(python=sys.executable))
                stub.chmod(0o755)
            log = directory / "commands.jsonl"
            github_env = directory / "github-env"
            env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}",
                       COMMAND_LOG=str(log), GITHUB_ENV=str(github_env),
                       TEST_OS="Ubuntu", TEST_CODENAME=codename, TEST_ARCH="amd64")
            env.pop("FAIL_COMMAND", None)
            env.pop("FAIL_SUDO", None)
            env.update(overrides)
            result = subprocess.run(["bash", str(SCRIPT), distro], env=env,
                                    capture_output=True, text=True, timeout=10)
            commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            exported = github_env.read_text() if github_env.exists() else ""
            return result, commands, exported

    def test_supported_distros_use_only_targeted_installs(self):
        for distro, codename, digest in (
            ("humble", "jammy", "110b9a462d55252decb8b7c816f61c2ba0d9890ce5fb93ac504e97cae5860d76"),
            ("jazzy", "noble", "f31d84adf5054c7d60ded0e82c0f776a77ea33af53d08f40b9ad7c94cca55296"),
        ):
            with self.subTest(distro=distro):
                result, commands, exported = self.run_setup(distro, codename)
                self.assertEqual(result.returncode, 0, result.stderr)
                privileged = [command[1:] for command in commands if command[0] == "sudo"]
                for command in privileged:
                    self.assertFalse({"upgrade", "dist-upgrade", "full-upgrade", "apt-mark"} & set(command))
                updates = [command for command in privileged if "update" in command]
                self.assertEqual(len(updates), 2)
                for command in updates:
                    self.assertIn("APT::Update::Error-Mode=any", command)
                    self.assertIn("Acquire::Retries=3", command)
                installs = [command for command in privileged if "apt-get" in command and "install" in command]
                self.assertEqual(len(installs), 2)
                for command in installs:
                    self.assertIn("--no-remove", command)
                    self.assertIn("--no-install-recommends", command)
                self.assertIn(f"ros-{distro}-desktop", installs[-1])
                self.assertIn("ros-dev-tools", installs[-1])
                self.assertIn("python3-colcon-common-extensions", installs[-1])
                self.assertIn("file", installs[-1])
                curl_index = next(i for i, command in enumerate(commands) if command[0] == "curl")
                url = f"https://github.com/ros-infrastructure/ros-apt-source/releases/download/1.3.0/ros2-apt-source_1.3.0.{codename}_all.deb"
                self.assertIn(url, commands[curl_index])
                checksum_index = next(i for i, command in enumerate(commands) if command[0] == "sha256sum")
                self.assertTrue(commands[checksum_index][-1].startswith(digest + "  "))
                dpkg_index = next(i for i, command in enumerate(commands) if command[:3] == ["sudo", "dpkg", "--install"])
                self.assertLess(curl_index, checksum_index)
                self.assertLess(checksum_index, dpkg_index)
                self.assertFalse(Path(commands[dpkg_index][-1]).exists(), "download must be cleaned up")
                self.assertEqual(exported, "LANG=en_US.UTF-8\nLC_ALL=en_US.UTF-8\n")

    def test_invalid_platforms_fail_before_mutation(self):
        for distro, codename, overrides in (
            ("rolling", "noble", {}), ("humble", "noble", {}),
            ("jazzy", "jammy", {}), ("humble", "jammy", {"TEST_OS": "Debian"}),
            ("humble", "jammy", {"TEST_ARCH": "arm64"}),
        ):
            with self.subTest(distro=distro, codename=codename, overrides=overrides):
                result, commands, _ = self.run_setup(distro, codename, **overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(command[0] == "sudo" for command in commands))

    def test_download_or_checksum_failure_does_not_install_source_package(self):
        for command in ("curl", "sha256sum"):
            with self.subTest(command=command):
                result, commands, _ = self.run_setup(FAIL_COMMAND=command)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(item[:2] == ["sudo", "dpkg"] for item in commands))
                self.assertFalse(any("ros-humble-desktop" in item for item in commands))

    def test_apt_failure_is_not_ignored_or_repaired_with_upgrade(self):
        for operation in ("update", "install"):
            with self.subTest(operation=operation):
                result, commands, _ = self.run_setup(FAIL_SUDO=operation)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(item[0] == "curl" for item in commands))
                self.assertFalse(any("upgrade" in item for item in commands))

    def test_workflow_calls_helper_and_retains_required_test_steps(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertNotIn("ros-tooling/setup-ros@", workflow)
        self.assertIn("bash scripts/setup_ros_ci.sh ${{ matrix.ros_distro }}", workflow)
        self.assertIn("test_setup_ros_ci.py", workflow)
        for step in ("colcon test-result --verbose", "test_lan_retry.py", "check_urdf_joint_names_",
                     "verify_ros2_msgs_deb_install.sh", "verify_ros2_deb_lifecycle.sh"):
            self.assertIn(step, workflow)


if __name__ == "__main__":
    unittest.main()
