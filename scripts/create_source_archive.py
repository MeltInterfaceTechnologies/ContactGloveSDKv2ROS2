#!/usr/bin/env python3
"""Create an authorized source snapshot including the pinned SDK, without Git history."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import tarfile

from source_revisions import ROOT, SNAPSHOT, revisions


def archive(repo, commit):
    data = subprocess.check_output(["git", "-C", str(repo), "archive", "--format=tar", commit])
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or PureWindowsPath(member.name).drive or "\\" in member.name
                    or ".." in path.parts or ".git" in path.parts
                    or member.issym() or member.islnk()):
                raise ValueError(f"unsafe source archive member: {member.name}")
            if member.isfile():
                yield member.name, tar.extractfile(member).read(), member.mode


def main(select_files=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new .tar.gz outside the checkout")
    args = parser.parse_args()
    destination = args.output.resolve()
    if ROOT in destination.parents or destination.exists():
        parser.error("output must be new and outside the checkout")
    rev = revisions()
    files = {}
    for name, content, mode in archive(ROOT, rev["ros2_commit"]):
        if name in files or name == SNAPSHOT:
            raise ValueError(f"duplicate source path: {name}")
        files[name] = (content, mode)
    for name, content, mode in archive(ROOT / "vendor/contactglove-sdk-v2", rev["sdk_commit"]):
        path = "vendor/contactglove-sdk-v2/" + name
        if path in files:
            raise ValueError(f"duplicate source path: {path}")
        files[path] = (content, mode)
    if select_files is not None:
        files = select_files(files)
    manifest = {"format": 1, **rev, "files": {name: hashlib.sha256(data).hexdigest()
                                              for name, (data, _) in sorted(files.items())}}
    files[SNAPSHOT] = ((json.dumps(manifest, indent=2) + "\n").encode(), 0o644)
    with tarfile.open(destination, "x:gz") as tar:
        for name, (content, mode) in sorted(files.items()):
            info = tarfile.TarInfo("ContactGloveSDKv2ROS2-source/" + name)
            info.mode, info.size = mode, len(content)
            tar.addfile(info, io.BytesIO(content))
    print(f"Created {destination} from {rev}")


if __name__ == "__main__":
    selection = None
    main(select_files=selection)
