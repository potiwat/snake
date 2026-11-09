"""
Validates the IOP Bioinspiration & Biomimetics LaTeX manuscript:
- Environment matching (\begin vs \end)
- Graphic assets existence
- Table input files existence
- Citation key resolution against references.bib
"""

import os
import re

def validate_manuscript():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pub_dir = os.path.join(base_dir, "results", "publication")
    tex_path = os.path.join(pub_dir, "manuscript_bioinspiration.tex")
    bib_path = os.path.join(pub_dir, "references.bib")

    if not os.path.exists(tex_path):
        print(f"[ERROR] LaTeX manuscript not found at {tex_path}")
        return False

    with open(tex_path, "r", encoding="utf-8") as f:
        tex_content = f.read()

    # 1. Check Environments
    begins = re.findall(r'\\begin\{([a-zA-Z0-9_\*]+)\}', tex_content)
    ends = re.findall(r'\\end\{([a-zA-Z0-9_\*]+)\}', tex_content)

    print(f"--- 1. Environment Balance Check ---")
    print(f"  Total \\begin: {len(begins)}, Total \\end: {len(ends)}")
    
    from collections import Counter
    b_count = Counter(begins)
    e_count = Counter(ends)
    all_envs = set(b_count.keys()).union(set(e_count.keys()))
    env_ok = True
    for env in sorted(all_envs):
        b = b_count[env]
        e = e_count[env]
        if b != e:
            print(f"  [MISMATCH] {env}: \\begin={b}, \\end={e}")
            env_ok = False
        else:
            print(f"  [OK] {env}: {b} pairs")

    # 2. Check Graphics Assets
    print(f"\n--- 2. Graphic Asset Existence Check ---")
    fig_matches = re.findall(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}', tex_content)
    figs_ok = True
    for fig in fig_matches:
        # Resolve path relative to pub_dir
        clean_fig = fig.replace('\\', '/')
        fig_full = os.path.join(pub_dir, clean_fig)
        
        # Also check with .png or .pdf extensions if omitted
        exists = os.path.exists(fig_full)
        if not exists:
            if os.path.exists(fig_full + ".png") or os.path.exists(fig_full + ".pdf"):
                exists = True
        
        if exists:
            print(f"  [OK] {fig}")
        else:
            print(f"  [MISSING] {fig} (checked {fig_full})")
            figs_ok = False

    # 3. Check Table Inputs
    print(f"\n--- 3. Table Input Existence Check ---")
    tbl_matches = re.findall(r'\\input\{([^}]+)\}', tex_content)
    tbls_ok = True
    for tbl in tbl_matches:
        clean_tbl = tbl.replace('\\', '/')
        tbl_full = os.path.join(pub_dir, clean_tbl)
        exists = os.path.exists(tbl_full) or os.path.exists(tbl_full + ".tex")
        if exists:
            print(f"  [OK] {tbl}")
        else:
            print(f"  [MISSING] {tbl}")
            tbls_ok = False

    # 4. Check Citations
    print(f"\n--- 4. Citation Resolution Check ---")
    bib_keys = set()
    if os.path.exists(bib_path):
        with open(bib_path, "r", encoding="utf-8") as f:
            bib_content = f.read()
        bib_keys = set(re.findall(r'@\w+\s*\{\s*([^,]+),', bib_content))
        print(f"  Found {len(bib_keys)} entries in references.bib")

    cite_matches = re.findall(r'\\cite\{([^}]+)\}', tex_content)
    all_cited = set()
    for cgroup in cite_matches:
        for k in cgroup.split(','):
            all_cited.add(k.strip())

    unresolved = all_cited - bib_keys
    if unresolved:
        print(f"  [WARN] {len(unresolved)} unresolved citation keys: {unresolved}")
    else:
        print(f"  [OK] All {len(all_cited)} cited keys resolved perfectly in references.bib!")

    print(f"\n=======================================================")
    if env_ok and figs_ok and tbls_ok and not unresolved:
        print("  [PASSED] LaTeX Manuscript verification: 100% CLEAN & READY")
    else:
        print("  [ALERT] Some items require minor path adjustment")
    print(f"=======================================================")

if __name__ == "__main__":
    validate_manuscript()
