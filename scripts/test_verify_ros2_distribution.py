#!/usr/bin/env python3
"""Synthetic archives exercise the distribution contract without ROS or dpkg."""

import io
import hashlib
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_ros2_distribution as verifier
import verify_distribution_licenses as licenses
from native_sdk_dependency import constraints


VERSION = "1.0.0"


def tar_bytes(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            member = tarfile.TarInfo("./" + name)
            member.size = len(content)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(content))
    return buffer.getvalue()


def deb_bytes(control, files):
    """A real ar/tar DEB, so tests cover the existing deb_files reader too."""
    output = bytearray(b"!<arch>\n")
    entries = {"debian-binary": b"2.0\n",
               "control.tar.gz": tar_bytes({"control": control.encode()}),
               "data.tar.gz": tar_bytes(files)}
    for name, content in entries.items():
        header = f"{name + '/':<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(content):<10}`\n"
        output.extend(header.encode("ascii"))
        output.extend(content)
        if len(content) % 2:
            output.extend(b"\n")
    return bytes(output)


class NativeProvenanceTests(unittest.TestCase):
    def test_notice_describes_rebuilt_sdk_provenance(self):
        notice = (licenses.ROOT / "NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("built from the pinned SDK source", notice)
        self.assertIn("distribution ZIP contains lib/sdk-provenance.json", notice)
        self.assertIn("It is generated for each build.", notice)
        self.assertNotIn("official CI", notice)

    def test_provenance_readme_distinguishes_source_and_zip(self):
        readme = (licenses.ROOT / "packaging/SDK_PROVENANCE.md").read_text(encoding="utf-8")
        self.assertIn("build generates `sdk-provenance.json` alongside the DEB", readme)
        self.assertIn("`SDK_BUILD_DIR`", readme)
        self.assertIn("at `lib/sdk-provenance.json` inside the distribution ZIP", readme)

    def setUp(self):
        self.sdk = "a" * 40
        self.ros = "b" * 40
        self.fields = {"Package": "contactglove-sdk-v2", "Version": "1.0.0-1noble+ros2.123.1",
                       "Architecture": "amd64", "Depends": "libc6"}
        control = "".join(f"{key}: {value}\n" for key, value in self.fields.items())
        prefix = "usr/share/doc/ContactGloveSDKv2/"
        files = {prefix + "LICENSE.md": (licenses.ROOT / "LICENSE.md").read_bytes(),
                 prefix + "NOTICE.md": b"Apache 2026 Melt Interface Technologies Inc.",
                 prefix + "THIRD_PARTY_NOTICES.md": (licenses.ROOT / "THIRD_PARTY_NOTICES.md").read_bytes()}
        self.deb = deb_bytes(control, files)
        self.provenance = {"kind": "ros2-ci-native-rebuild", "sha256": hashlib.sha256(self.deb).hexdigest(),
                           "sdk_commit": self.sdk, "ros2_commit": self.ros, "build_id": "123.1",
                           "codename": "noble", "control": self.fields.copy(),
                           "cmake": "cmake fixture", "compiler": "compiler fixture",
                           "build_type": "Release", "filename": "fixture.deb",
                           "build_packages": ["cmake=fixture"],
                           "cmake_options": ["CONTACTGLOVE_PACKAGE_DEB=ON", "CONTACTGLOVE_DEB_DISTRIBUTION=noble"]}
        self.git = mock.patch.object(licenses, "revisions", return_value={"sdk_commit": self.sdk, "ros2_commit": self.ros})

    def test_valid_provenance(self):
        with self.git:
            licenses.verify_cpp(self.deb, self.provenance)

    def test_rejects_changed_bytes_and_commits(self):
        for key, value in (("sha256", "0" * 64), ("sdk_commit", "c" * 40), ("ros2_commit", "d" * 40)):
            with self.subTest(key=key):
                changed = dict(self.provenance, **{key: value})
                with mock.patch.object(licenses, "revisions", return_value={"sdk_commit": self.sdk, "ros2_commit": self.ros}):
                    with self.assertRaises(ValueError):
                        licenses.verify_cpp(self.deb, changed)

    def test_rejects_reused_old_revision(self):
        changed = dict(self.provenance, build_id="123.2")
        with self.git, self.assertRaisesRegex(ValueError, "version or architecture"):
            licenses.verify_cpp(self.deb, changed)

    def test_rejects_noncanonical_provenance_build_ids(self):
        for bad_id in ("123.01", "0123.1", "0.1", "1.0"):
            with self.subTest(build_id=bad_id):
                changed = dict(self.provenance, build_id=bad_id)
                with mock.patch.object(licenses, "revisions", return_value={"sdk_commit": self.sdk, "ros2_commit": self.ros}):
                    with self.assertRaisesRegex(ValueError, "invalid build ID"):
                        licenses.verify_cpp(self.deb, changed)


class DistributionFixture:
    def __init__(self, distro="humble", codename="jammy", sdk_version="1.0.0", ros_version=VERSION):
        self.distro, self.codename = distro, codename
        self.root = f"ContactGloveSDKv2ROS2-{ros_version}-{distro}-amd64"
        self.docs = {
            "README.md": b"# ContactGlove\n[Japanese](README_JA.md)\n[Manual](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2/user-manual)\n```bash\nsudo apt install ./lib/contactglove-sdk-v2_*.deb ./contactglove-ros2-msgs_*.deb ./contactglove-ros2-bridge_*.deb\nsudo apt install ./contactglove-ros2-msgs_*.deb\n```\n",
            "README_JA.md": b"# ContactGlove\n[English](README.md)\n[Manual](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2/user-manual)\n```bash\nsudo apt install ./lib/contactglove-sdk-v2_*.deb ./contactglove-ros2-msgs_*.deb ./contactglove-ros2-bridge_*.deb\nsudo apt install ./contactglove-ros2-msgs_*.deb\n```\n",
            "LICENSE.md": b"License fixture\n",
            "NOTICE.md": b"Notice fixture\n",
            "THIRD_PARTY_NOTICES.md": b"Third party fixture\n",
        }
        self.readmes = verifier.READMES
        self.files = {name: content for name, content in self.docs.items()
                      if name in self.readmes + verifier.LEGAL_DOCS}
        self.files["install/setup.bash"] = b"# setup\n"
        self.files["lib/README.md"] = f"# SDK\n[Provenance](sdk-provenance.json)\nThe ROS 2 SDK version is {ros_version}.\n".encode()
        self.files["lib/sdk-provenance.json"] = b"{}"
        self.controls = {}
        self.payloads = {}
        self.deb_names = {}
        for role, packages in (("bridge", ("contact_glove",)), ("msgs", ("contact_glove_msgs",))):
            deps = f"ros-{distro}-std-msgs, ros-{distro}-geometry-msgs, ros-{distro}-rosidl-default-runtime"
            if role == "bridge":
                deps += f", contactglove-ros2-msgs (= {ros_version}-1{codename}+ros2.123.1), " + ", ".join(constraints(f"{sdk_version}-1{codename}+ros2.123.1", codename))
            self.controls[role] = f"Package: contactglove-ros2-{role}\nVersion: {ros_version}-1{codename}+ros2.123.1\nArchitecture: amd64\nDepends: {deps}\n"
            if role == "msgs":
                self.controls[role] += "Breaks: contactglove-ros2-bridge (<< 0.2.4)\nReplaces: contactglove-ros2-bridge (<< 0.2.4)\n"
            self.deb_names[role] = f"contactglove-ros2-{role}_{ros_version}-1{codename}+ros2.123.1_amd64.deb"
            payload = self.payloads[role] = {}
            for package in packages:
                prefix = f"opt/ros/{distro}/share/{package}/"
                for name, content in self.docs.items():
                    payload[prefix + name] = content
                payload[prefix + "package.xml"] = f"<package><name>{package}</name><version>{ros_version}</version></package>".encode()
                payload[f"opt/ros/{distro}/share/ament_index/resource_index/packages/{package}"] = b""
                payload[f"opt/ros/{distro}/share/ament_index/resource_index/parent_prefix_path/{package}"] = b"/opt/ros/" + distro.encode()
            if role in verifier.ROLES:
                self.files.update({"install/" + name.removeprefix(f"opt/ros/{distro}/"): content
                                   for name, content in payload.items()})
        self.controls["cpp"] = f"Package: contactglove-sdk-v2\nVersion: {sdk_version}-1{codename}+ros2.123.1\nArchitecture: amd64\nDepends: libc6\n"
        self.deb_names["cpp"] = f"lib/contactglove-sdk-v2_{sdk_version}-1{codename}+ros2.123.1_amd64.deb"
        self.payloads["cpp"] = {"usr/share/doc/ContactGloveSDKv2/README.md": b"# SDK\n[License](LICENSE.md)\n",
                                "usr/share/doc/ContactGloveSDKv2/LICENSE.md": b"License fixture\n"}

    def write(self, directory):
        files = dict(self.files)
        for role in self.controls:
            files[self.deb_names[role]] = deb_bytes(self.controls[role], self.payloads[role])
        path = Path(directory) / (self.root + ".zip")
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in files.items():
                archive.writestr(self.root + "/" + name, content)
        return path


class DistributionTests(unittest.TestCase):
    def check_fixture(self, fixture, error=None):
        with tempfile.TemporaryDirectory() as directory:
            path = fixture.write(directory)
            before = path.read_bytes()
            if error:
                with self.assertRaisesRegex(ValueError, error):
                    verifier.verify_zip(path, fixture.distro, fixture.codename)
            else:
                self.assertIn("Verified complete", verifier.verify_zip(path, fixture.distro, fixture.codename))
            self.assertEqual(before, path.read_bytes(), "verification must not modify the archive")

    def test_complete_humble_and_jazzy_archives(self):
        for distro, codename in verifier.PAIRS.items():
            with self.subTest(distro=distro):
                self.check_fixture(DistributionFixture(distro, codename))

    def test_rejects_runtime_from_another_ros2_release(self):
        for distro, codename in verifier.PAIRS.items():
            for ros_version, sdk_version in (("1.0.0", "0.4.4"), ("1.0.0", "1.0.1")):
                with self.subTest(distro=distro, ros_version=ros_version, sdk_version=sdk_version):
                    fixture = DistributionFixture(distro, codename, sdk_version=sdk_version, ros_version=ros_version)
                    self.check_fixture(fixture, "requires C\\+\\+ runtime")

    def test_rejects_unrecognized_release_contract(self):
        self.check_fixture(DistributionFixture(ros_version="2.0.0"), "unsupported ROS2 release contract")

    def test_rejects_incorrect_native_dependency_alternatives(self):
        for distro, codename in verifier.PAIRS.items():
            expected = constraints(f"1.0.0-1{codename}+ros2.123.1", codename)[0]
            for dependency in ("contactglove-sdk-v2",
                               "contactglove-sdk-v2 (>= 0.4.4)",
                               f"contactglove-sdk-v2 (>= 1.0.0-0{codename})",
                               expected.replace(codename, "noble" if codename == "jammy" else "jammy"),
                               expected.replace("ros2.123.1", "ros2.123.2"),
                               expected + " | alternative-sdk"):
                with self.subTest(distro=distro, dependency=dependency):
                    fixture = DistributionFixture(distro, codename)
                    fixture.controls["bridge"] = fixture.controls["bridge"].replace(expected, dependency)
                    self.check_fixture(fixture, r"bridge must require the tested same-distro C\+\+ versions and ABI upper bound")

    def test_rejects_missing_or_incorrect_native_abi_bound(self):
        for replacement in ("", "contactglove-sdk-v2 (<< 3.0.0)",
                            "contactglove-sdk-v2 (<< 2.0.0) | alternative-sdk"):
            fixture = DistributionFixture()
            fixture.controls["bridge"] = fixture.controls["bridge"].replace("contactglove-sdk-v2 (<< 2.0.0)", replacement)
            self.check_fixture(fixture, r"bridge must require the tested same-distro C\+\+ versions and ABI upper bound")

    def test_rejects_mixed_native_build_id(self):
        fixture = DistributionFixture()
        fixture.controls["cpp"] = fixture.controls["cpp"].replace("ros2.123.1", "ros2.123.2")
        fixture.deb_names["cpp"] = fixture.deb_names["cpp"].replace("ros2.123.1", "ros2.123.2")
        self.check_fixture(fixture, "build IDs differ")

    def test_rejects_noncanonical_native_build_id(self):
        for bad_id in ("123.01", "0123.1", "0.1", "1.0"):
            with self.subTest(build_id=bad_id):
                fixture = DistributionFixture()
                fixture.controls["cpp"] = fixture.controls["cpp"].replace("123.1", bad_id)
                fixture.deb_names["cpp"] = fixture.deb_names["cpp"].replace("123.1", bad_id)
                self.check_fixture(fixture, r"C\+\+ runtime metadata")

    def test_rejects_noncanonical_ros_build_id(self):
        for bad_id in ("123.01", "0123.1", "0.1", "1.0"):
            with self.subTest(build_id=bad_id):
                fixture = DistributionFixture()
                fixture.controls["bridge"] = fixture.controls["bridge"].replace("123.1", bad_id)
                fixture.deb_names["bridge"] = fixture.deb_names["bridge"].replace("123.1", bad_id)
                self.check_fixture(fixture, "bridge: version does not match")

    def test_missing_msgs_deb(self):
        fixture = DistributionFixture()
        del fixture.controls["msgs"]
        self.check_fixture(fixture, "exactly two root ROS DEBs")

    def test_missing_generated_sdk_provenance(self):
        fixture = DistributionFixture()
        del fixture.files["lib/sdk-provenance.json"]
        self.check_fixture(fixture, "missing or empty document: lib/sdk-provenance.json")

    def test_rejects_stale_bundled_sdk_provenance_version(self):
        fixture = DistributionFixture()
        fixture.files["lib/README.md"] = fixture.files["lib/README.md"].replace(VERSION.encode(), b"0.2.3")
        self.check_fixture(fixture, "bundled SDK provenance README must match")

    def test_rejects_overlapping_file_ownership(self):
        fixture = DistributionFixture()
        fixture.payloads["bridge"]["opt/ros/humble/lib/duplicate.so"] = b"library"
        fixture.payloads["msgs"]["opt/ros/humble/lib/duplicate.so"] = b"library"
        self.check_fixture(fixture, "overlapping DEB file ownership")

    def test_rejects_missing_or_unversioned_msgs_dependency(self):
        for dependency in ("", "contactglove-ros2-msgs", "contactglove-ros2-msgs (>= 0.2.3)"):
            fixture = DistributionFixture()
            fixture.controls["bridge"] = fixture.controls["bridge"].replace(
                f"contactglove-ros2-msgs (= {VERSION}-1jammy+ros2.123.1)", dependency)
            self.check_fixture(fixture, "bridge must depend on exact msgs version")

    def test_rejects_missing_or_unbounded_transition(self):
        for field in ("Breaks", "Replaces"):
            fixture = DistributionFixture()
            fixture.controls["msgs"] = fixture.controls["msgs"].replace(
                f"{field}: contactglove-ros2-bridge (<< 0.2.4)", f"{field}: contactglove-ros2-bridge")
            self.check_fixture(fixture, field + " must cover only pre-split")

    def test_missing_common_readme_in_msgs(self):
        fixture = DistributionFixture()
        del fixture.payloads["msgs"]["opt/ros/humble/share/contact_glove_msgs/README_JA.md"]
        self.check_fixture(fixture, "missing or empty document")

    def test_broken_link_in_root_readme(self):
        fixture = DistributionFixture()
        fixture.files["README.md"] += b"[Broken](missing.md)\n"
        self.check_fixture(fixture, "broken relative link.*README.md")

    def test_broken_link_in_installed_readme(self):
        fixture = DistributionFixture()
        fixture.files["install/share/contact_glove_msgs/README.md"] += b"[Broken](docs/user_manual.md)\n"
        self.check_fixture(fixture, "broken relative link.*install/share/contact_glove_msgs")

    def test_broken_link_in_msgs_deb(self):
        fixture = DistributionFixture()
        fixture.payloads["msgs"]["opt/ros/humble/share/contact_glove_msgs/README.md"] += b"[Broken](../api.md)\n"
        self.check_fixture(fixture, "msgs DEB: broken relative link")

    def test_broken_link_in_cpp_deb(self):
        fixture = DistributionFixture()
        fixture.payloads["cpp"]["usr/share/doc/ContactGloveSDKv2/README.md"] += b"[Broken](missing.md)\n"
        self.check_fixture(fixture, r"C\+\+ runtime DEB: broken relative link")

    def test_rejects_independent_msgs_readme(self):
        fixture = DistributionFixture()
        fixture.files["README_MSGS_EN.md"] = b"# Old guide"
        self.check_fixture(fixture, "independent msgs README")

    def test_rejects_build_instructions(self):
        for command in (b"bash scripts/package_ros2_msgs.sh humble jammy", b"colcon build --merge-install", b"git clone https://example.com/repo"):
            with self.subTest(command=command):
                fixture = DistributionFixture()
                fixture.files["README_JA.md"] += command
                self.check_fixture(fixture, "repository-only build instructions")

    def test_rejects_shipped_packaging_script(self):
        fixture = DistributionFixture()
        fixture.files["scripts/package_ros2.sh"] = b"#!/bin/sh\n"
        self.check_fixture(fixture, "repository-only packaging script")

    def test_rejects_blanket_apt_glob(self):
        fixture = DistributionFixture()
        fixture.files["README_JA.md"] += b"\n```bash\nsudo apt install ./*.deb\n```\n"
        self.check_fixture(fixture, "unsafe or non-role-specific")

    def test_allows_negative_blanket_glob_warning(self):
        fixture = DistributionFixture()
        # The warning is valid, and all installed copies must match the root.
        for files in (fixture.files, *fixture.payloads.values()):
            for name in files:
                if name == "README_JA.md" or name.endswith("/README_JA.md"):
                    files[name] += b"\nDo not run `sudo apt install ./*.deb`.\n"
        self.check_fixture(fixture)

    def test_rejects_cross_distro_command(self):
        fixture = DistributionFixture()
        fixture.files["README_JA.md"] += b"\n```bash\nsudo apt install ./contactglove-ros2-msgs_*noble_amd64.deb\n```\n"
        self.check_fixture(fixture, "must match exactly its one root DEB")

    def test_rejects_different_deb_versions(self):
        fixture = DistributionFixture()
        fixture.controls["msgs"] = fixture.controls["msgs"].replace(VERSION, "9.9.9")
        fixture.deb_names["msgs"] = fixture.deb_names["msgs"].replace(VERSION, "9.9.9")
        self.check_fixture(fixture, "versions differ")

    def test_rejects_wrong_architecture(self):
        fixture = DistributionFixture()
        fixture.controls["msgs"] = fixture.controls["msgs"].replace("amd64", "arm64")
        self.check_fixture(fixture, "Architecture must be amd64")

    def test_rejects_wrong_codename(self):
        fixture = DistributionFixture()
        fixture.controls["msgs"] = fixture.controls["msgs"].replace("jammy", "noble")
        self.check_fixture(fixture, "version does not match jammy")

    def test_rejects_control_filename_mismatch(self):
        fixture = DistributionFixture()
        fixture.deb_names["msgs"] = fixture.deb_names["msgs"].replace(VERSION, "9.9.9")
        self.check_fixture(fixture, "filename/control mismatch")

    def test_rejects_sdk_dependency_in_msgs(self):
        fixture = DistributionFixture()
        fixture.controls["msgs"] += "Pre-Depends: contactglove-sdk-v2\n"
        self.check_fixture(fixture, "unexpected bridge/SDK dependency")

    def test_rejects_other_distro_dependency(self):
        fixture = DistributionFixture()
        fixture.controls["msgs"] += "Pre-Depends: ros-jazzy-rclcpp\n"
        self.check_fixture(fixture, "different ROS distro")

    def test_rejects_bridge_ament_resource_in_msgs(self):
        fixture = DistributionFixture()
        fixture.payloads["msgs"]["opt/ros/humble/share/ament_index/resource_index/packages/contact_glove"] = b""
        self.check_fixture(fixture, "overlapping DEB file ownership")

    def test_rejects_other_ament_resource_in_msgs(self):
        fixture = DistributionFixture()
        fixture.payloads["msgs"]["opt/ros/humble/share/ament_index/resource_index/rosidl_interfaces/alien"] = b""
        self.check_fixture(fixture, "unexpected ament resource entry")

    def test_rejects_sdk_library_in_msgs(self):
        fixture = DistributionFixture()
        fixture.payloads["msgs"]["opt/ros/humble/lib/libContactGloveSDKv2.so"] = b"binary"
        self.check_fixture(fixture, "bridge or SDK payload")

    def test_rejects_base_prefix_setup_files(self):
        fixture = DistributionFixture()
        fixture.payloads["msgs"]["opt/ros/humble/setup.bash"] = b"setup"
        self.check_fixture(fixture, "must not overwrite base ROS setup")

    def test_rejects_changed_msgs_legal_document(self):
        fixture = DistributionFixture()
        fixture.payloads["msgs"]["opt/ros/humble/share/contact_glove_msgs/LICENSE.md"] += b"changed"
        self.check_fixture(fixture, "legal document differs")

    def test_rejects_changed_msgs_common_readme(self):
        fixture = DistributionFixture()
        fixture.payloads["msgs"]["opt/ros/humble/share/contact_glove_msgs/README.md"] += b"different"
        self.check_fixture(fixture, "README differs")

    def test_rejects_changed_installed_readme(self):
        fixture = DistributionFixture()
        fixture.files["install/share/contact_glove/README_JA.md"] += b"changed"
        self.check_fixture(fixture, "README differs from ZIP root")

    def test_rejects_obsolete_manual_or_api(self):
        for name in ("user_manual.md", "user_manual_ja.md", "api.md"):
            fixture = DistributionFixture()
            fixture.files["docs/" + name] = b"old full guide"
            self.check_fixture(fixture, "full manuals and API reference belong on the Web")

    def test_readme_requires_both_installation_choices(self):
        for name in verifier.READMES:
            fixture = DistributionFixture()
            fixture.files[name] = b"# Missing installation commands"
            self.check_fixture(fixture, "missing explicit bridge DEB install command")

    def test_readme_requires_subscriber_only_installation(self):
        for name in verifier.READMES:
            fixture = DistributionFixture()
            fixture.files[name] = fixture.files[name].replace(
                b"sudo apt install ./contactglove-ros2-msgs_*.deb\n", b"")
            self.check_fixture(fixture, "missing subscriber-only msgs DEB install command")

    def test_rejects_wrong_native_sdk_distro(self):
        fixture = DistributionFixture()
        fixture.controls["cpp"] = fixture.controls["cpp"].replace("jammy", "noble")
        self.check_fixture(fixture, r"C\+\+ runtime metadata")

    def test_rejects_additional_nested_deb(self):
        fixture = DistributionFixture()
        fixture.files["extras/old.deb"] = b"deb"
        self.check_fixture(fixture, "unexpected additional DEB")

    def test_rejects_noncanonical_zip_path(self):
        fixture = DistributionFixture()
        fixture.files["../escape"] = b"escape"
        self.check_fixture(fixture, "unsafe or non-canonical")


class MarkdownTests(unittest.TestCase):
    def test_inline_reference_html_and_percent_encoded_links(self):
        text = '# Heading\n[inline](a.md#heading "title")\n![image](fig/a(1).png)\n[ref][manual]\n[manual]: <a.md#heading>\n<img src="fig/a%281%29.png">\n[space](<a b.md>)\n'
        files = {"README.md": text.encode(), "a.md": b"# Heading\n", "fig/a(1).png": b"image", "a b.md": b"# Space"}
        verifier.verify_links(files, "test")

    def test_ignores_fenced_and_inline_code_links(self):
        verifier.verify_links({"README.md": b"```md\n[broken](not-real)\n```\n`[broken](not-real)`\n"}, "test")

    def test_broken_anchor_fails(self):
        with self.assertRaisesRegex(ValueError, "broken Markdown anchor"):
            verifier.verify_links({"README.md": b"[bad](#missing)\n# Present"}, "test")

    def test_duplicate_heading_anchor_resolves(self):
        verifier.verify_links({"README.md": b"[second](#heading-1)\n# Heading\n# Heading\n"}, "test")

    def test_undefined_explicit_reference_fails(self):
        with self.assertRaisesRegex(ValueError, "undefined Markdown link reference"):
            verifier.verify_links({"README.md": b"[bad][missing]"}, "test")

    def test_external_links_are_not_fetched(self):
        verifier.verify_links({"README.md": b"[web](https://example.invalid/a#no-anchor)\n[mail](mailto:a@example.invalid)\n"}, "test")

    def test_escape_from_payload_fails(self):
        with self.assertRaisesRegex(ValueError, "escapes payload"):
            verifier.verify_links({"README.md": b"[bad](../elsewhere.md)"}, "test")

    def test_readme_needs_both_role_commands(self):
        with self.assertRaisesRegex(ValueError, "explicitly include msgs"):
            verifier.verify_consumer_docs({"README.md": b"```bash\nsudo apt install ./contactglove-ros2-bridge_*.deb\n```"},
                                          {"bridge": f"contactglove-ros2-bridge_{VERSION}-1jammy+ros2.123.1_amd64.deb", "msgs": f"contactglove-ros2-msgs_{VERSION}-1jammy+ros2.123.1_amd64.deb"}, "test")


if __name__ == "__main__":
    unittest.main()
