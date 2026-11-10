#!/usr/bin/env python3
"""Read-only validation of a complete same-distro ContactGlove ROS 2 ZIP.

Usage: verify_ros2_distribution.py <zip> <humble|jazzy> <jammy|noble>
The archive and embedded DEBs are inspected in memory; nothing is installed.
"""

import argparse
from email.parser import Parser
import fnmatch
from html import unescape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

from native_sdk_dependency import constraints
from verify_distribution_licenses import BUILD_ID_REGEX, deb_files, reject_old_legal


PAIRS = {"humble": "jammy", "jazzy": "noble"}
# Supported ROS2/C++ release pairs, checked independently of archive metadata.
ROS2_SDK_VERSIONS = {"1.0.0": "1.0.0"}
PACKAGES = ("contact_glove", "contact_glove_msgs")
READMES = ("README.md", "README_JA.md")
LEGAL_DOCS = ("LICENSE.md", "NOTICE.md", "THIRD_PARTY_NOTICES.md")
ROLES = ("bridge", "msgs")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(name):
    """Accept canonical archive-relative paths only, never traversal aliases."""
    path = PurePosixPath(name)
    require(bool(name) and not path.is_absolute() and ".." not in path.parts
            and "\\" not in name and posixpath.normpath(name) == name,
            f"unsafe or non-canonical archive path: {name}")


def require_files(files, prefix, names):
    for name in names:
        require(bool(files.get(prefix + name)), f"missing or empty document: {prefix + name}")


def without_code_blocks(text):
    result = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            result.append("")
        else:
            result.append(line if fence is None else "")
    return "\n".join(result)


def shell_commands(text):
    """Only executable examples count; prose can warn against unsafe commands."""
    commands = []
    fence = None
    shell = False
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})([^\s]*)\s*$", line)
        if match:
            token, language = match.groups()
            if fence is None:
                fence = token
                shell = language.lower() in ("", "sh", "bash", "shell", "console", "zsh")
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
                shell = False
        elif shell:
            commands.append(line)
    return re.sub(r"\\\s*\n", " ", "\n".join(commands))


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for key, value in attrs
                          if key in ("href", "src") and value is not None)


def markdown_links(text):
    """Read inline, image, reference and HTML links, excluding code examples."""
    text = without_code_blocks(text)
    text = re.sub(r"(`+).*?\1", "", text)
    definitions = {}
    for match in re.finditer(r"^\s{0,3}\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))", text, re.M):
        definitions[" ".join(match.group(1).lower().split())] = match.group(2) or match.group(3)
    links = list(definitions.values())
    # Balance parentheses in destinations, including names like image(1).png.
    for match in re.finditer(r"!?\[[^\]\n]*\]\(\s*", text):
        start = match.end()
        if text[start:start + 1] == "<":
            end = text.find(">", start + 1)
            require(end != -1, "unterminated Markdown link destination")
            links.append(text[start + 1:end])
            continue
        index, depth = start, 0
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char.isspace() and depth == 0:
                break
            index += 1
        if index > start:
            links.append(re.sub(r"\\(.)", r"\1", text[start:index]))
    for match in re.finditer(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]", text):
        label = " ".join((match.group(2) or match.group(1)).lower().split())
        require(label in definitions, f"undefined Markdown link reference: {label}")
    html = HTMLLinks()
    html.feed(text)
    return links + html.links


def markdown_anchors(text):
    """GitHub-style heading anchors, including duplicate-heading suffixes."""
    text = without_code_blocks(text)
    anchors = set(re.findall(r"\b(?:id|name)=[\"']([^\"']+)", text))
    counts = {}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
        setext = index + 1 < len(lines) and re.match(r"^\s{0,3}(?:=+|-+)\s*$", lines[index + 1])
        if not heading and not (setext and line.strip()):
            continue
        label = heading.group(1) if heading else line.strip()
        label = re.sub(r"<[^>]*>", "", unescape(label)).lower()
        label = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", label)
        label = "".join(char for char in label if char.isalnum() or char in " _-")
        label = label.replace(" ", "-")
        count = counts.get(label, 0)
        counts[label] = count + 1
        anchors.add(label if count == 0 else f"{label}-{count}")
    return anchors


def verify_links(files, label):
    for name, data in files.items():
        if not name.lower().endswith(".md"):
            continue
        text = data.decode("utf-8")
        for link in markdown_links(text):
            target = urlsplit(unescape(link))
            if target.scheme or target.netloc:
                continue
            path = unquote(target.path)
            require(not path.startswith("/"), f"{label}: non-portable link in {name}: {link}")
            destination = posixpath.normpath(posixpath.join(posixpath.dirname(name), path)) if path else name
            require(destination != ".." and not destination.startswith("../"),
                    f"{label}: link escapes payload in {name}: {link}")
            exists = destination in files or any(item.startswith(destination.rstrip("/") + "/") for item in files)
            require(exists, f"{label}: broken relative link in {name}: {link}")
            if target.fragment and destination.lower().endswith(".md") and destination in files:
                require(unquote(target.fragment) in markdown_anchors(files[destination].decode("utf-8")),
                        f"{label}: broken Markdown anchor in {name}: {link}")


def verify_consumer_docs(files, root_debs, label, readmes=READMES):
    for name, data in files.items():
        require(not PurePosixPath(name).name.upper().startswith("README_MSGS"),
                f"{label}: independent msgs README must not ship: {name}")
        require(not re.search(r"(?:^|/)scripts/package[^/]*", name),
                f"{label}: repository-only packaging script shipped: {name}")
        require(PurePosixPath(name).name not in ("user_manual.md", "user_manual_ja.md", "api.md"),
                f"{label}: full manuals and API reference belong on the Web: {name}")
        if PurePosixPath(name).name not in readmes:
            continue
        # lib/README.md describes native SDK provenance, not a user guide.
        if name.endswith("lib/README.md"):
            continue
        text = data.decode("utf-8")
        require(not re.search(r"(?:scripts/package\w*|\bcolcon\s+build\b|\bgit\s+clone\b|\bcmake\s+(?:--build|-S)\b)", text),
                f"{label}: repository-only build instructions in {name}")
        commands = shell_commands(text)
        subscriber_command = False
        for command in re.findall(r"(?:sudo\s+)?apt(?:-get)?\s+(?:[^\n]*?\s)?install\s+([^\n]+)", commands):
            local_debs = re.findall(r"(?:\./)?[^\s`'\"<>]*\.deb", command)
            if len(local_debs) == 1 and local_debs[0].startswith("./contactglove-ros2-msgs_"):
                subscriber_command = True
            for pattern in local_debs:
                require(pattern.startswith("./contactglove-ros2-bridge_")
                        or pattern.startswith("./contactglove-ros2-msgs_")
                        or pattern.startswith("./lib/contactglove-sdk-v2_"),
                        f"{label}: unsafe or non-role-specific apt DEB pattern in {name}: {pattern}")
                if pattern.startswith("./lib/"):
                    continue
                role = "bridge" if pattern.startswith("./contactglove-ros2-bridge_") else "msgs"
                matches = [item for item in root_debs.values() if fnmatch.fnmatchcase(item, pattern[2:])]
                require(matches == [root_debs[role]],
                        f"{label}: {role} install pattern must match exactly its one root DEB in {name}: {pattern}")
            if any(pattern.startswith("./contactglove-ros2-bridge_") for pattern in local_debs):
                require(any(pattern.startswith("./contactglove-ros2-msgs_") for pattern in local_debs)
                        and any(pattern.startswith("./lib/contactglove-sdk-v2_") for pattern in local_debs),
                        f"{label}: bridge command must explicitly include msgs and C++ runtime in {name}")
        # Both role-specific installation choices belong in each minimal README.
        if PurePosixPath(name).name in readmes:
            for role in ROLES:
                require(re.search(r"apt(?:-get)?\s+install\s+[^\n]*\./contactglove-ros2-" + role + r"_[^\s`]*\.deb", commands),
                        f"{label}: missing explicit {role} DEB install command in {name}")
            require(subscriber_command,
                    f"{label}: missing subscriber-only msgs DEB install command in {name}")


def control_fields(data, label):
    control = deb_files(data, "control")
    require("control" in control, f"{label}: missing DEB control")
    fields = Parser().parsestr(control["control"].decode("utf-8"))
    for field in ("Package", "Version", "Architecture"):
        require(bool(fields[field]), f"{label}: missing control {field}")
    return fields


def dependency_names(control):
    text = ",".join(control.get(field, "") for field in ("Depends", "Pre-Depends", "Recommends"))
    return re.findall(r"(?:^|[,|])\s*([a-z0-9][a-z0-9+.-]*)", text)


def verify_ros_payload(files, distro, version, packages, label, readmes=READMES):
    prefix = f"opt/ros/{distro}/"
    for name in files:
        safe_path(name)
        require(name.startswith(prefix), f"{label}: unexpected file outside {prefix}: {name}")
        require("/" in name.removeprefix(prefix),
                f"{label}: DEB must not overwrite base ROS setup files: {name}")
    manifest_names = {name for name in files if name.endswith("/package.xml")}
    expected = {prefix + f"share/{package}/package.xml" for package in packages}
    require(manifest_names == expected, f"{label}: unexpected ROS package manifests: {sorted(manifest_names)}")
    for package in packages:
        doc_prefix = prefix + f"share/{package}/"
        require_files(files, doc_prefix, readmes + LEGAL_DOCS)
        manifest = ET.fromstring(files[doc_prefix + "package.xml"])
        require(manifest.findtext("name") == package and manifest.findtext("version") == version,
                f"{label}: manifest name/version mismatch: {package}")
    index = prefix + "share/ament_index/resource_index/"
    package_entries = {name.removeprefix(index + "packages/") for name in files if name.startswith(index + "packages/")}
    require(package_entries == set(packages), f"{label}: unexpected ament package entries: {sorted(package_entries)}")
    for name in files:
        if name.startswith(index):
            require(PurePosixPath(name).name in packages,
                    f"{label}: unexpected ament resource entry: {name}")
    if packages == ("contact_glove_msgs",):
        for name in files:
            require(not re.search(r"(?:^|/)contact_glove(?:/|$)|ContactGloveSDK|contactglove-sdk|libcontact_glove(?!_msgs)", name),
                    f"{label}: bridge or SDK payload in msgs-only DEB: {name}")
    if packages == ("contact_glove",):
        for name in files:
            require("contact_glove_msgs" not in name and "ContactGloveSDK" not in name,
                    f"{label}: msgs or SDK payload in bridge-only DEB: {name}")
    return {name.removeprefix(prefix): content for name, content in files.items()}


def verify_zip(path, distro, codename, *, sdk_versions=None, readmes=READMES):
    sdk_versions = ROS2_SDK_VERSIONS if sdk_versions is None else sdk_versions
    require(PAIRS.get(distro) == codename, f"unsupported ROS/Ubuntu pair: {distro}/{codename}")
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        require(len(names) == len(set(names)), "duplicate ZIP member")
        for name in names:
            safe_path(name)
        prefix = path.stem + "/"
        require(bool(names) and all(name.startswith(prefix) for name in names), "ZIP must have one root matching its filename")
        files = {name.removeprefix(prefix): archive.read(name) for name in names}
    require_files(files, "", ("README.md",) + LEGAL_DOCS)
    require_files(files, "lib/", ("README.md", "sdk-provenance.json"))
    require("install/setup.bash" in files, "missing relocatable install/setup.bash")
    root_deb_names = [name for name in files if "/" not in name and name.endswith(".deb")]
    require(len(root_deb_names) == 2, "expected exactly two root ROS DEBs (bridge and msgs)")
    root_debs = {}
    controls = {}
    payloads = {}
    for role in ROLES:
        matches = [name for name in root_deb_names if name.startswith(f"contactglove-ros2-{role}_")]
        require(len(matches) == 1, f"expected exactly one root {role} DEB")
        name = root_debs[role] = matches[0]
        fields = controls[role] = control_fields(files[name], role)
        require(fields["Package"] == f"contactglove-ros2-{role}", f"{role}: incorrect Package")
        require(fields["Architecture"] == "amd64", f"{role}: Architecture must be amd64")
        require(re.fullmatch(r".+-1" + re.escape(codename) + r"\+ros2\." + BUILD_ID_REGEX, fields["Version"]),
                f"{role}: version does not match {codename}")
        require(name == f'{fields["Package"]}_{fields["Version"]}_{fields["Architecture"]}.deb', f"{role}: filename/control mismatch")
        for dependency in dependency_names(fields):
            require(not dependency.startswith("ros-") or dependency.startswith(f"ros-{distro}-"),
                    f"{role}: dependency on a different ROS distro: {dependency}")
        payloads[role] = deb_files(files[name])
    require(controls["bridge"]["Version"] == controls["msgs"]["Version"], "bridge and msgs versions differ")
    require(f'contactglove-ros2-msgs (= {controls["msgs"]["Version"]})'
            in controls["bridge"].get("Depends", ""), "bridge must depend on exact msgs version")
    for field in ("Breaks", "Replaces"):
        require(controls["msgs"].get(field) == "contactglove-ros2-bridge (<< 0.2.4)",
                f"msgs: {field} must cover only pre-split bridges")
    version, build_id = re.fullmatch(r"(.+)-1" + re.escape(codename) + r"\+ros2\.(" + BUILD_ID_REGEX + ")",
                                     controls["msgs"]["Version"]).groups()
    require_files(files, "", readmes + LEGAL_DOCS)
    require(path.stem == f"ContactGloveSDKv2ROS2-{version}-{distro}-amd64", "ZIP name/version/distro/architecture mismatch")
    require(re.search(r"The ROS 2 SDK version is " + re.escape(version) + r"\.",
                      files.get("lib/README.md", b"").decode("utf-8")),
            "bundled SDK provenance README must match ROS2 package version")
    for dependency in dependency_names(controls["msgs"]):
        require(not re.search(r"contact.?glove|diving.?station|sdk", dependency, re.I),
                f"msgs: unexpected bridge/SDK dependency: {dependency}")
    cpp_names = [name for name in files if name.startswith("lib/") and name.endswith(".deb")]
    require(len(cpp_names) == 1, "expected exactly one C++ runtime DEB in lib/")
    cpp_name = cpp_names[0]
    cpp = control_fields(files[cpp_name], "C++ runtime")
    require(cpp["Package"] == "contactglove-sdk-v2" and cpp["Architecture"] == "amd64"
            and re.fullmatch(r".+-1" + re.escape(codename) + r"\+ros2\." + BUILD_ID_REGEX, cpp["Version"]),
            "C++ runtime metadata does not match distro/architecture")
    require(version in sdk_versions, f"unsupported ROS2 release contract: {version}")
    expected_sdk = sdk_versions[version]
    require(cpp["Version"].split("-", 1)[0] == expected_sdk,
            f"ROS2 {version} requires C++ runtime {expected_sdk}")
    require(cpp["Version"].endswith("-1" + codename + "+ros2." + build_id),
            "C++ and ROS2 DEB build IDs differ")
    require(cpp_name == f'lib/{cpp["Package"]}_{cpp["Version"]}_amd64.deb', "C++ runtime filename/control mismatch")
    require("contactglove-sdk-v2" in dependency_names(controls["bridge"]), "bridge must depend on C++ runtime")
    native_dependencies = [item.strip() for item in controls["bridge"].get("Depends", "").split(",")]
    require(all(item in native_dependencies for item in constraints(cpp["Version"], codename)),
            "bridge must require the tested same-distro C++ versions and ABI upper bound")
    ownership = {role: set(deb_files(files[root_debs[role]], include_links=True)) for role in ROLES}
    ownership["cpp"] = set(deb_files(files[cpp_name], include_links=True))
    for left, right in (("bridge", "msgs"), ("bridge", "cpp"), ("msgs", "cpp")):
        require(not ownership[left] & ownership[right],
                f"{left}/{right}: overlapping DEB file ownership: {sorted(ownership[left] & ownership[right])}")
    require(set(name for name in files if name.endswith(".deb")) == set(root_deb_names + cpp_names), "unexpected additional DEB in ZIP")
    documentation_sets = [("ZIP", files)]
    for role in ROLES:
        package_names = ("contact_glove",) if role == "bridge" else ("contact_glove_msgs",)
        normalized = verify_ros_payload(payloads[role], distro, version, package_names, role, readmes)
        documentation_sets.append((role + " DEB", normalized))
    for package in PACKAGES:
        require_files(files, f"install/share/{package}/", readmes + LEGAL_DOCS)
    for label, payload in documentation_sets:
        verify_links(payload, label)
        verify_consumer_docs(payload, root_debs, label, readmes)
        for name, data in payload.items():
            if PurePosixPath(name).name in readmes and not name.endswith("lib/README.md"):
                require(data == files[PurePosixPath(name).name],
                        f"{label}: README differs from ZIP root: {name}")
            if PurePosixPath(name).name in LEGAL_DOCS:
                require(data == files[PurePosixPath(name).name],
                        f"{label}: legal document differs from ZIP root: {name}")
    # Native runtime docs are also user-facing; check their relative links.
    cpp_files = deb_files(files[cpp_name])
    reject_old_legal(cpp_files)
    verify_links(cpp_files, "C++ runtime DEB")
    return f"Verified complete {distro}/{codename} distribution: {path}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("distro", choices=tuple(PAIRS))
    parser.add_argument("codename", choices=tuple(PAIRS.values()))
    args = parser.parse_args()
    try:
        print(verify_zip(args.archive, args.distro, args.codename))
    except (ValueError, KeyError, OSError, ET.ParseError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Distribution verification failed: {error}\n")


if __name__ == "__main__":
    main()
