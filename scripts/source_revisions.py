#!/usr/bin/env python3
"""Resolve and verify the source revisions in a checkout or source snapshot."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ".source-revisions.json"
GENERATED = {"build", "install", "log", "dist"}


def allowed_generated(path):
    parts = PurePosixPath(path).parts
    return bool(parts) and (parts[0] in GENERATED or parts[:2] == ("scripts", "__pycache__"))


def untracked(repo):
    # No --exclude-standard: ignored files can still be installed by CMake.
    output = subprocess.check_output(["git", "-C", str(repo), "ls-files", "--others",
                                      "--directory", "--no-empty-directory", "-z"], text=True)
    return [path for path in output.split("\0") if path]


def revisions():
    if (ROOT / ".git").exists():
        def git(*args):
            return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()
        if subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--"], check=False).returncode:
            raise ValueError("ROS2 tracked files or submodule have uncommitted changes")
        extra = [path for path in untracked(ROOT) if not allowed_generated(path)]
        if extra:
            raise ValueError(f"ROS2 checkout contains untracked files: {extra[0]}")
        sdk = git("ls-tree", "HEAD", "vendor/contactglove-sdk-v2").split()[2]
        sdk_root = ROOT / "vendor/contactglove-sdk-v2"
        actual = subprocess.check_output(["git", "-C", str(sdk_root), "rev-parse", "HEAD"], text=True).strip()
        extra = untracked(sdk_root)
        if extra:
            raise ValueError(f"SDK checkout contains untracked files: {extra[0]}")
        dirty = subprocess.check_output(["git", "-C", str(sdk_root), "status", "--porcelain"], text=True)
        if sdk != actual or dirty:
            raise ValueError("SDK submodule is missing, dirty or does not match the recorded commit")
        return {"ros2_commit": git("rev-parse", "HEAD"), "sdk_commit": sdk}
    manifest = json.loads((ROOT / SNAPSHOT).read_text())
    if manifest.get("format") != 1:
        raise ValueError("unsupported source snapshot manifest")
    actual = {}
    for file in ROOT.rglob("*"):
        relative = file.relative_to(ROOT)
        if allowed_generated(relative.as_posix()) or str(relative) == SNAPSHOT:
            continue
        if file.is_symlink():
            raise ValueError(f"source snapshot contains a symlink: {relative}")
        if file.is_file():
            actual[relative.as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    if actual != manifest["files"]:
        raise ValueError("source snapshot does not match its file checksums")
    for key in ("ros2_commit", "sdk_commit"):
        if len(manifest[key]) != 40 or any(c not in "0123456789abcdef" for c in manifest[key]):
            raise ValueError("invalid source revision")
    return {key: manifest[key] for key in ("ros2_commit", "sdk_commit")}


if __name__ == "__main__":
    try:
        print(json.dumps(revisions()))
    except (OSError, ValueError, KeyError, IndexError, subprocess.CalledProcessError) as exc:
        print(f"Cannot verify SDK source: {exc}", file=sys.stderr)
        sys.exit(1)
