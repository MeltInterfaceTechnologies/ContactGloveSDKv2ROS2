#!/usr/bin/env python3
"""Accept only the tested official SDK or this ZIP's same-distro rebuild."""
import re
import sys


def constraints(version, codename):
    if codename not in ("jammy", "noble"):
        raise ValueError("unsupported SDK distribution")
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)-1" + codename + r"\+ros2\.[1-9]\d*\.[1-9]\d*", version)
    if not match:
        raise ValueError("unexpected rebuilt SDK version")
    source = ".".join(match.groups())
    # Debian sorts Ubuntu codenames as ordinary version text. A range from
    # 0jammy to ABI 2 would also accept 0noble; exact alternatives cannot.
    return (f"contactglove-sdk-v2 (= {source}-0{codename}) | contactglove-sdk-v2 (= {version})",
            f"contactglove-sdk-v2 (<< {int(match[1]) + 1}.0.0)")


if __name__ == "__main__":
    print(", ".join(constraints(*sys.argv[1:])))
