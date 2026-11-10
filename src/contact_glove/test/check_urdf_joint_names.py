#!/usr/bin/env python3
# Copyright (c) 2026 Melt Interface Technologies Inc.
# SPDX-License-Identifier: Apache-2.0
"""
Check that a contact_glove hand urdf.xacro's joint names match to_joint_state().

JOINT_SUFFIXES below must be kept in sync by hand with kJointStateSuffixes in
src/contact_glove/src/conversions.cpp; there is no single source of truth
shared between the C++ and the URDF/xacro files.
"""
import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET

JOINT_SUFFIXES = [
    'thumb_cmc_joint', 'thumb_mcp_joint', 'thumb_ip_joint', 'thumb_tilt_joint',
    'index_mcp_joint', 'index_pip_joint', 'index_dip_joint', 'index_tilt_joint',
    'middle_mcp_joint', 'middle_pip_joint', 'middle_dip_joint', 'middle_tilt_joint',
    'ring_mcp_joint', 'ring_pip_joint', 'ring_dip_joint', 'ring_tilt_joint',
    'little_mcp_joint', 'little_pip_joint', 'little_dip_joint', 'little_tilt_joint',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xacro', required=True, help='path to the xacro executable')
    parser.add_argument('--urdf', required=True, help='path to a *_hand.urdf.xacro file')
    parser.add_argument('--side', required=True, choices=['left', 'right'])
    args = parser.parse_args()

    expanded = subprocess.run(
        [args.xacro, args.urdf], check=True, capture_output=True, text=True).stdout
    root = ET.fromstring(expanded)

    actuated = sorted(
        joint.get('name') for joint in root.findall('joint')
        if joint.get('type') != 'fixed')
    expected = sorted(f'{args.side}_{suffix}' for suffix in JOINT_SUFFIXES)

    if actuated != expected:
        print(f'Joint name mismatch for {args.urdf}', file=sys.stderr)
        print(f'  expanded: {actuated}', file=sys.stderr)
        print(f'  expected: {expected}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
