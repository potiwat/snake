"""
Copies official IOP class files to results/publication/ root.
"""

import shutil
import os

pub_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "publication")
src_dir = os.path.join(pub_dir, "iop_official_template")

for fname in ["iopjournal.cls", "orcid.pdf"]:
    src = os.path.join(src_dir, fname)
    dst = os.path.join(pub_dir, fname)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"[OK] Copied {fname} to {pub_dir}")

