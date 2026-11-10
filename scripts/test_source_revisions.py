#!/usr/bin/env python3
"""Exercise provenance checks against real, isolated Git worktrees."""
import subprocess
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import source_revisions


class SourceRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "ros2"
        self.sdk = self.root / "vendor/contactglove-sdk-v2"
        self.root.mkdir()
        self.sdk.mkdir(parents=True)
        self.git(self.root, "init", "-q")
        self.git(self.sdk, "init", "-q")
        (self.sdk / ".gitignore").write_text("build/\n")
        (self.sdk / "tracked.txt").write_text("SDK\n")
        self.commit(self.sdk)
        sha = self.git(self.sdk, "rev-parse", "HEAD").strip()
        (self.root / ".gitignore").write_text("build/\ninstall/\nlog/\ndist/\n")
        launch = self.root / "src/contact_glove/launch"
        launch.mkdir(parents=True)
        (launch / "tracked.launch.xml").write_text("<launch/>\n")
        (self.root / "scripts").mkdir()
        (self.root / "scripts/tracked.py").write_text("# fixture\n")
        self.git(self.root, "add", ".gitignore", "src", "scripts")
        self.git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{sha},vendor/contactglove-sdk-v2")
        self.commit(self.root, add=False)
        self.root_patch = mock.patch.object(source_revisions, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    @staticmethod
    def git(root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE)

    def commit(self, root, add=True):
        if add:
            self.git(root, "add", ".")
        self.git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")

    def test_clean_and_allowed_generated_directories(self):
        for name in ("build", "install", "log", "dist", "scripts/__pycache__"):
            directory = self.root / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "generated").write_text("generated\n")
        self.assertEqual(source_revisions.revisions()["sdk_commit"], self.git(self.sdk, "rev-parse", "HEAD").strip())

    def test_rejects_untracked_ros_source_even_when_ignored(self):
        for name in ("extra.launch.xml", "build/hidden.xml", "__pycache__/hidden.pyc"):
            with self.subTest(name=name):
                path = self.root / "src/contact_glove/launch" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("unrecorded\n")
                with self.assertRaisesRegex(ValueError, "untracked"):
                    source_revisions.revisions()
                path.unlink()

    def test_rejects_untracked_sdk_source_even_when_ignored(self):
        for name in ("examples/extra.txt", "build/hidden.txt"):
            with self.subTest(name=name):
                path = self.sdk / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("unrecorded\n")
                with self.assertRaisesRegex(ValueError, "untracked"):
                    source_revisions.revisions()
                path.unlink()

    def test_snapshot_rejects_extra_cache_in_installable_source(self):
        snapshot = Path(self.temp.name) / "snapshot"
        launch = snapshot / "src/contact_glove/launch"
        launch.mkdir(parents=True)
        content = b"<launch/>\n"
        (launch / "tracked.launch.xml").write_bytes(content)
        manifest = {"format": 1, "ros2_commit": "a" * 40, "sdk_commit": "b" * 40,
                    "files": {"src/contact_glove/launch/tracked.launch.xml": hashlib.sha256(content).hexdigest()}}
        (snapshot / source_revisions.SNAPSHOT).write_text(json.dumps(manifest))
        with mock.patch.object(source_revisions, "ROOT", snapshot):
            self.assertEqual(source_revisions.revisions()["sdk_commit"], "b" * 40)
            extra = launch / "__pycache__/extra.pyc"
            extra.parent.mkdir()
            extra.write_bytes(b"unrecorded")
            with self.assertRaisesRegex(ValueError, "file checksums"):
                source_revisions.revisions()


class PackageBuildIdTests(unittest.TestCase):
    def test_packagers_reject_noncanonical_build_ids_before_building(self):
        scripts = Path(__file__).resolve().parent
        commands = (("build_cpp_sdk.sh", "noble", "/tmp/not-used"),
                    ("package_ros2.sh", "jazzy", "noble"),
                    ("package_ros2_msgs.sh", "jazzy", "noble"))
        for bad_id in ("123.01", "0123.1", "0.1", "1.0"):
            for script, *args in commands:
                with self.subTest(build_id=bad_id, script=script):
                    env = dict(os.environ, PACKAGE_BUILD_ID=bad_id)
                    result = subprocess.run(["bash", str(scripts / script), *args], env=env,
                                            capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("invalid PACKAGE_BUILD_ID", result.stderr)


if __name__ == "__main__":
    unittest.main()
