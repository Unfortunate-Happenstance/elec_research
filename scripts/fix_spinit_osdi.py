#!/usr/bin/env python3
"""Patch ngspice spinit to enable OSDI and load heracles.osdi.

Run inside Docker container:
  python3 /workspace/scripts/fix_spinit_osdi.py
"""
import re, shutil, sys

SPINIT = "/usr/local/share/ngspice/scripts/spinit"
HERACLES_OSDI = "/usr/local/lib/ngspice/heracles.osdi"

with open(SPINIT) as f:
    content = f.read()

# 1. Flip unset -> set for osdi_enabled
content = content.replace("unset osdi_enabled", "set osdi_enabled")

# 2. Insert heracles osdi as the FIRST entry in the if-block,
#    right after the line "if $?osdi_enabled" (with any trailing whitespace/newline)
MARKER = "if $?osdi_enabled"
INSERT  = f" osdi {HERACLES_OSDI}"

if INSERT in content:
    print(f"heracles osdi line already present in spinit — no change needed")
elif MARKER not in content:
    print(f"ERROR: could not find '{MARKER}' in {SPINIT}", file=sys.stderr)
    sys.exit(1)
else:
    # Replace first occurrence: insert our line right after the marker + newline
    content = content.replace(
        MARKER + "\n",
        MARKER + "\n" + INSERT + "\n",
        1,  # only first occurrence
    )
    print(f"Inserted: {INSERT}")

with open(SPINIT, "w") as f:
    f.write(content)

# Verify
with open(SPINIT) as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "osdi_enabled" in line or "heracles" in line:
        print(f"  {i+1:3d}: {line}", end="")

print("\nspinit patched OK")
