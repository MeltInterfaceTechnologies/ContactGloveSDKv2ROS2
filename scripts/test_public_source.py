#!/usr/bin/env python3
"""Verify source snapshot integrity, documentation and SDK compatibility."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

import create_source_archive as exporter
import source_revisions
from native_sdk_dependency import constraints


class PublicSourceTests(unittest.TestCase):
    def test_public_documentation_contract(self):
        root = Path(__file__).resolve().parent.parent
        for directory in (root, root / "packaging", root / "scripts/mock_server"):
            english = (directory / "README.md").read_text()
            japanese = (directory / "README_JA.md").read_text()
            self.assertIn("English | [日本語](README_JA.md)", english)
            self.assertIn("[English](README.md) | 日本語", japanese)
            self.assertFalse((directory / "README_EN.md").exists())
            if directory.name != "mock_server":
                for text in (english, japanese):
                    self.assertEqual(text.splitlines()[0], "# ContactGlove ROS2 SDK V2")
                    self.assertIn("ContactGlove3 Pro", text)
                    self.assertNotIn("ContactGlove3 Pro ROS2 SDK", text)
                    self.assertIn("DivingStation v2", text)
                    self.assertNotIn("alpha5", text)

    def test_development_documentation_languages(self):
        root = Path(__file__).resolve().parent.parent
        english = (root / "DEVELOPMENT.md").read_text()
        japanese = (root / "DEVELOPMENT_JA.md").read_text()
        self.assertIn("English | [日本語](DEVELOPMENT_JA.md)", english)
        self.assertIn("[English](DEVELOPMENT.md) | 日本語", japanese)
        self.assertIn("ContactGlove ROS2 SDK V2", english.splitlines()[0])
        self.assertIn("ContactGlove ROS2 SDK V2", japanese.splitlines()[0])
        self.assertIn("[DEVELOPMENT.md](DEVELOPMENT.md)", (root / "README.md").read_text())
        self.assertIn("[DEVELOPMENT_JA.md](DEVELOPMENT_JA.md)", (root / "README_JA.md").read_text())
        self.assertNotIn("(Japanese)", (root / "README.md").read_text())

    def test_export_includes_both_revisions_and_verifies_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            sdk = root / "vendor/contactglove-sdk-v2"
            sdk.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "init", "-q", str(sdk)], check=True)
            (sdk / "CMakeLists.txt").write_text("project(public-sdk)\n")
            for path in ("README.md", "scripts/verify_ros2_deb_lifecycle.sh", "scripts/ros2_deb_test_common.sh"):
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(path + "\n")
            def commit(repo):
                subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
                subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture", "-c",
                                "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
                return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            sdk_sha = commit(sdk)
            root_sha = commit(root)
            target = Path(temp) / "source.tar.gz"
            revisions = {"ros2_commit": root_sha, "sdk_commit": sdk_sha}
            with mock.patch.object(exporter, "ROOT", root), mock.patch.object(exporter, "revisions", return_value=revisions), \
                    mock.patch.object(sys, "argv", ["create_source_archive.py", str(target)]):
                exporter.main()
            with tarfile.open(target) as archive:
                files = {member.name.split("/", 1)[1]: archive.extractfile(member).read()
                         for member in archive if member.isfile()}
            for path in ("scripts/verify_ros2_deb_lifecycle.sh", "scripts/ros2_deb_test_common.sh",
                         "vendor/contactglove-sdk-v2/CMakeLists.txt"):
                self.assertIn(path, files)
            manifest = json.loads(files.pop(source_revisions.SNAPSHOT))
            self.assertEqual(manifest["files"], {name: hashlib.sha256(data).hexdigest() for name, data in files.items()})
            self.assertEqual(manifest["sdk_commit"], sdk_sha)

    def test_public_workflow_keeps_current_checks(self):
        root = Path(__file__).resolve().parent.parent
        workflow = (root / ".github/workflows/ci.yml").read_text()
        for name in ("Verify ZIP msgs alone in a fresh ROS image",
                     "Verify ZIP bridge lifecycle in a fresh ROS image",
                     "Verify bridge lifecycle with the official C++ Release DEB",
                     "Checksum validated package for handoff"):
            self.assertIn(name, workflow)
        self.assertIn("https://github.com/MeltInterfaceTechnologies/ContactGloveSDKv2Cpp.git",
                      (root / ".gitmodules").read_text())

    def test_unsafe_archive_paths_and_links_are_rejected(self):
        for name, kind in (("../outside", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
                           ("C:/absolute", tarfile.REGTYPE), ("folder\\file", tarfile.REGTYPE),
                           (".git/config", tarfile.REGTYPE), ("link", tarfile.SYMTYPE),
                           ("link", tarfile.LNKTYPE)):
            with self.subTest(name=name, kind=kind):
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode="w") as archive:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "target" if kind != tarfile.REGTYPE else ""
                    archive.addfile(member)
                with mock.patch.object(exporter.subprocess, "check_output", return_value=buffer.getvalue()):
                    with self.assertRaisesRegex(ValueError, "unsafe source archive member"):
                        list(exporter.archive(Path("repo"), "a" * 40))

    def test_duplicate_source_paths_and_manifest_are_rejected(self):
        for entries in ([ ("README.md", b"one", 0o644), ("README.md", b"two", 0o644) ],
                        [ (source_revisions.SNAPSHOT, b"{}", 0o644) ]):
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / "source.tar.gz"
                with mock.patch.object(exporter, "archive", return_value=iter(entries)), \
                        mock.patch.object(exporter, "revisions", return_value={"ros2_commit": "a" * 40, "sdk_commit": "b" * 40}), \
                        mock.patch.object(sys, "argv", ["create_source_archive.py", str(target)]):
                    with self.assertRaisesRegex(ValueError, "duplicate source path"):
                        exporter.main()
                self.assertFalse(target.exists())

    def test_unverified_checkout_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "source.tar.gz"
            with mock.patch.object(exporter, "revisions", side_effect=ValueError("source mismatch")), \
                    mock.patch.object(sys, "argv", ["create_source_archive.py", str(target)]):
                with self.assertRaisesRegex(ValueError, "source mismatch"):
                    exporter.main()
            self.assertFalse(target.exists())


class NativeSdkDependencyTests(unittest.TestCase):
    def test_official_and_rebuilt_packages_meet_bounds(self):
        for codename in ("jammy", "noble"):
            lower, upper = constraints(f"1.0.0-1{codename}+ros2.123.1", codename)
            self.assertEqual(lower, f"contactglove-sdk-v2 (= 1.0.0-0{codename}) | contactglove-sdk-v2 (= 1.0.0-1{codename}+ros2.123.1)")
            self.assertEqual(upper, "contactglove-sdk-v2 (<< 2.0.0)")
            for version in (f"1.0.0-0{codename}", f"1.0.0-1{codename}+ros2.123.1"):
                self.assertEqual(subprocess.call(["dpkg", "--compare-versions", version, "ge", f"1.0.0-0{codename}"]), 0)
                self.assertEqual(subprocess.call(["dpkg", "--compare-versions", version, "lt", "2.0.0"]), 0)
            self.assertNotEqual(subprocess.call(["dpkg", "--compare-versions", "0.4.4-0" + codename, "ge", f"1.0.0-0{codename}"]), 0)
            self.assertNotEqual(subprocess.call(["dpkg", "--compare-versions", "2.0.0-0" + codename, "lt", "2.0.0"]), 0)

    def test_real_debian_solver_rejects_other_distro_and_untested_versions(self):
        with tempfile.TemporaryDirectory() as temp:
            status = Path(temp) / "status"
            for codename, other in (("jammy", "noble"), ("noble", "jammy")):
                depends = ", ".join(constraints(f"1.0.0-1{codename}+ros2.123.1", codename))
                versions = {f"1.0.0-0{codename}": True,
                            f"1.0.0-1{codename}+ros2.123.1": True,
                            f"1.0.0-0{other}": False,
                            f"1.0.0-1{other}+ros2.123.1": False,
                            f"1.0.0-1{codename}+ros2.123.2": False,
                            f"0.4.4-0{codename}": False,
                            f"1.0.1-0{codename}": False,
                            f"2.0.0-0{codename}": False}
                for version, accepted in versions.items():
                    with self.subTest(codename=codename, version=version):
                        status.write_text("Package: contactglove-sdk-v2\nStatus: install ok installed\n"
                                          f"Architecture: amd64\nVersion: {version}\n\n")
                        result = subprocess.run(["dpkg-checkbuilddeps", "-I", "--admindir=" + temp,
                                                 "-a", "amd64", "-d", depends, "/dev/null"],
                                                capture_output=True, text=True)
                        self.assertEqual(result.returncode == 0, accepted, result.stderr)

    def test_rejects_wrong_codename_or_noncanonical_versions(self):
        for version, codename in (("1.0.0-1jammy+ros2.123.1", "noble"),
                                  ("1.0.0-1jammy+ros2.123.01", "jammy"),
                                  ("1.0.0-1jammy+ros2.123.1", "focal")):
            with self.assertRaises(ValueError):
                constraints(version, codename)


if __name__ == "__main__":
    unittest.main()
