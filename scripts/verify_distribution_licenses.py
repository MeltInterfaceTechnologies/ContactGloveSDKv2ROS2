#!/usr/bin/env python3
"""Inspect actual ROS 2 ZIP/DEB payloads without installing or extracting them."""

import argparse
from email.parser import Parser
import hashlib
import io
import json
import re
from pathlib import Path
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from source_revisions import revisions
from native_sdk_dependency import constraints


ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = ("LICENSE.md", "NOTICE.md", "THIRD_PARTY_NOTICES.md")
BUILD_ID_REGEX = r"[1-9][0-9]*\.[1-9][0-9]*"


def deb_files(data, member_prefix="data", include_links=False):
    if not data.startswith(b"!<arch>\n"):
        raise ValueError("not a Debian ar archive")
    position = 8
    while position < len(data):
        header = data[position:position + 60]
        if len(header) != 60 or header[58:] != b"`\n":
            raise ValueError("invalid ar header")
        size = int(header[48:58])
        name = header[:16].decode("ascii").strip().rstrip("/")
        payload = data[position + 60:position + 60 + size]
        if len(payload) != size:
            raise ValueError("truncated ar member")
        position += 60 + size + size % 2
        if name.startswith(member_prefix + ".tar"):
            # Ubuntu's dpkg defaults to zstd, which Python 3.10/3.12 tarfile
            # cannot decode. Let dpkg read it without installing/extracting.
            if name.endswith(".zst"):
                with tempfile.TemporaryDirectory() as temporary:
                    archive_path = Path(temporary) / "package.deb"
                    archive_path.write_bytes(data)
                    payload = subprocess.check_output(
                        ["dpkg-deb", "--fsys-tarfile" if member_prefix == "data"
                         else "--ctrl-tarfile", str(archive_path)])
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
                return {member.name.removeprefix("./"):
                        (archive.extractfile(member).read() if member.isfile()
                         else member.linkname.encode())
                        for member in archive.getmembers()
                        if member.isfile() or (include_links and (member.issym() or member.islnk()))}
    raise ValueError(f"DEB is missing {member_prefix}.tar")


def reject_old_legal(files):
    for name in files:
        if any(word in name.lower() for word in ("termofuse", "privacypolicy")):
            raise ValueError(f"obsolete first-party legal file: {name}")


def require_documents(files, prefix):
    for name in DOCUMENTS:
        if files.get(prefix + name) != (ROOT / name).read_bytes():
            raise ValueError(f"missing or changed document: {prefix + name}")


def verify_cpp(data, provenance):
    digest = hashlib.sha256(data).hexdigest()
    if provenance.get("kind") != "ros2-ci-native-rebuild" or provenance.get("sha256") != digest:
        raise ValueError("C++ DEB checksum does not match build provenance")
    expected = revisions()
    if provenance.get("sdk_commit") != expected["sdk_commit"] or provenance.get("ros2_commit") != expected["ros2_commit"]:
        raise ValueError("build provenance source commits do not match this checkout")
    if not re.fullmatch(BUILD_ID_REGEX, provenance.get("build_id", "")):
        raise ValueError("invalid build ID in provenance")
    if not all(provenance.get(field) for field in ("cmake", "compiler", "build_type", "filename")):
        raise ValueError("incomplete build conditions in provenance")
    if (provenance["build_type"] != "Release" or not provenance.get("build_packages")
            or provenance.get("cmake_options") != ["CONTACTGLOVE_PACKAGE_DEB=ON",
                "CONTACTGLOVE_DEB_DISTRIBUTION=" + provenance.get("codename", "")]):
        raise ValueError("invalid or incomplete SDK build conditions")
    control = Parser().parsestr(deb_files(data, "control")["control"].decode())
    for field in ("Package", "Version", "Architecture", "Depends"):
        if control[field] != provenance["control"][field]:
            raise ValueError(f"C++ DEB {field} differs from recorded provenance")
    if (control["Package"] != "contactglove-sdk-v2" or control["Architecture"] != "amd64"
            or provenance.get("codename") not in ("jammy", "noble")
            or not control["Version"].endswith("-1" + provenance["codename"] + "+ros2." + provenance["build_id"])):
        raise ValueError("C++ DEB version or architecture does not match build provenance")
    files = deb_files(data)
    reject_old_legal(files)
    prefix = "usr/share/doc/ContactGloveSDKv2/"
    if files.get(prefix + "LICENSE.md", b"").replace(b"\r\n", b"\n") != (ROOT / "LICENSE.md").read_bytes().replace(b"\r\n", b"\n"):
        raise ValueError("C++ DEB does not contain the standard Apache license")
    notice = files.get(prefix + "NOTICE.md", b"")
    if b"Apache" not in notice or b"2026 Melt Interface Technologies Inc." not in notice:
        raise ValueError("C++ DEB is missing the license/attribution notice")
    expected = (ROOT / "THIRD_PARTY_NOTICES.md").read_bytes().split(b"## oscpack", 1)[1]
    actual = files.get(prefix + "THIRD_PARTY_NOTICES.md", b"").split(b"## oscpack", 1)
    if len(actual) != 2 or actual[1].replace(b"\r\n", b"\n") != expected.replace(b"\r\n", b"\n"):
        raise ValueError("C++ DEB oscpack notice differs from the preserved text")
    return provenance


def verify_bridge(data, cpp_package):
    control = Parser().parsestr(deb_files(data, "control")["control"].decode())
    suffix = "-1" + cpp_package["codename"] + "+ros2." + cpp_package["build_id"]
    if not control["Version"].endswith(suffix):
        raise ValueError("ROS 2 DEB has an unexpected Debian revision")
    dependencies = [item.strip() for item in control["Depends"].split(",")]
    if not all(item in dependencies for item in constraints(cpp_package["control"]["Version"], cpp_package["codename"])):
        raise ValueError("ROS 2 DEB must require the tested same-distro C++ SDK versions and ABI upper bound")
    if control["Architecture"] != cpp_package["control"]["Architecture"]:
        raise ValueError("ROS 2 and C++ DEB architectures differ")
    verify_ros_licenses(data, "contact_glove")


def verify_ros_licenses(data, package):
    files = deb_files(data)
    reject_old_legal(files)
    manifests = [name for name in files if name.endswith(f"/share/{package}/package.xml")]
    if len(manifests) != 1:
        raise ValueError(f"expected one installed manifest for {package}")
    manifest = manifests[0]
    if ET.fromstring(files[manifest]).findtext("license") != "Apache-2.0":
        raise ValueError(f"wrong installed license metadata: {manifest}")
    require_documents(files, manifest.removesuffix("package.xml"))


def verify_zip(path):
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    reject_old_legal(files)
    prefix = path.stem + "/"
    require_documents(files, prefix)
    for package in ("contact_glove", "contact_glove_msgs"):
        require_documents(files, prefix + f"install/share/{package}/")
    cpp = [name for name in files if name.startswith(prefix + "lib/contactglove-sdk-v2_")
           and name.endswith(".deb")]
    bridge = [name for name in files if name.startswith(prefix + "contactglove-ros2-bridge_")
              and name.endswith(".deb")]
    msgs = [name for name in files if name.startswith(prefix + "contactglove-ros2-msgs_")
            and name.endswith(".deb")]
    if len(cpp) != 1 or len(bridge) != 1 or len(msgs) != 1:
        raise ValueError("expected one C++ runtime, one ROS 2 bridge and one msgs DEB")
    provenance = json.loads(files[prefix + "lib/sdk-provenance.json"])
    if provenance.get("filename") != Path(cpp[0]).name:
        raise ValueError("bundled C++ filename differs from build provenance")
    cpp_package = verify_cpp(files[cpp[0]], provenance)
    bridge_control = Parser().parsestr(deb_files(files[bridge[0]], "control")["control"].decode())
    bridge_version = bridge_control["Version"].removesuffix(
        "-1" + cpp_package["codename"] + "+ros2." + cpp_package["build_id"])
    expected_readme = (ROOT / "packaging/SDK_PROVENANCE.md").read_bytes().replace(b"@ROS2_VERSION@", bridge_version.encode())
    if files.get(prefix + "lib/README.md") != expected_readme:
        raise ValueError("missing or changed SDK provenance README")
    verify_bridge(files[bridge[0]], cpp_package)
    verify_ros_licenses(files[msgs[0]], "contact_glove_msgs")
    print(f"Verified Apache documents, manifests, third-party notices and provenance: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpp-deb", type=Path)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("archives", type=Path, nargs="*")
    args = parser.parse_args()
    if not args.cpp_deb and not args.archives:
        parser.error("provide --cpp-deb or a distribution ZIP")
    if args.cpp_deb:
        if not args.provenance:
            parser.error("--cpp-deb requires --provenance")
        verify_cpp(args.cpp_deb.read_bytes(), json.loads(args.provenance.read_text()))
        print(f"Verified C++ runtime license documents: {args.cpp_deb}")
    for archive in args.archives:
        verify_zip(archive)
