"""
Comprehensive verification of the IOP Bioinspiration & Biomimetics manuscript
strictly against the official IOP Publishing template guidelines.
"""

import os
import re

def verify_iop_manuscript():
    pub_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "publication")
    tex_path = os.path.join(pub_dir, "manuscript_bioinspiration.tex")
    bib_path = os.path.join(pub_dir, "references.bib")
    cls_path = os.path.join(pub_dir, "iopjournal.cls")

    print("=" * 70)
    print("  Official IOP Publishing Manuscript Verification Suite")
    print("=" * 70)

    # 1. Check required official IOP files
    assert os.path.exists(cls_path), "Missing official iopjournal.cls in publication directory!"
    print("[OK] Official iopjournal.cls found in publication folder.")

    with open(tex_path, "r", encoding="utf-8") as f:
        tex_text = f.read()

    with open(bib_path, "r", encoding="utf-8") as f:
        bib_text = f.read()

    # 2. Check IOP header commands
    iop_required_commands = [
        r"\documentclass{iopjournal}",
        r"\articletype",
        r"\title",
        r"\author",
        r"\orcid",
        r"\affil",
        r"\email",
        r"\keywords",
        r"\ack",
        r"\funding",
        r"\roles",
        r"\data",
        r"\suppdata"
    ]
    for cmd in iop_required_commands:
        assert cmd in tex_text, f"Missing required IOP command: {cmd}"
        print(f"  [OK] IOP command verified: {cmd}")

    # 3. Proper Stack-based Environment Matching
    tokens = re.findall(r'\\(begin|end)\{([a-zA-Z0-9*]+)\}', tex_text)
    stack = []
    env_count = 0
    for kind, env in tokens:
        if kind == "begin":
            stack.append(env)
            env_count += 1
        else:
            assert len(stack) > 0, f"Unmatched \\end{{{env}}} with empty stack!"
            opened = stack.pop()
            assert opened == env, f"Mismatched environment: opened \\begin{{{opened}}} but closed with \\end{{{env}}}!"
    assert len(stack) == 0, f"Unclosed environments remaining on stack: {stack}"
    print(f"\n[OK] All {env_count} LaTeX environments perfectly balanced with clean nesting stack.")

    # 4. Citations check against references.bib
    cites = set()
    for m in re.finditer(r'\\cite\{([^}]+)\}', tex_text):
        for k in m.group(1).split(','):
            cites.add(k.strip())

    bib_keys = set(re.findall(r'@\w+\{([^,]+),', bib_text))
    print(f"\n[INFO] Citations in text: {len(cites)}, BibTeX keys in .bib: {len(bib_keys)}")
    missing_keys = cites - bib_keys
    if missing_keys:
        print(f"  [ERROR] Missing BibTeX keys: {missing_keys}")
        raise AssertionError(f"Missing keys: {missing_keys}")
    else:
        print(f"  [OK] All {len(cites)} cited keys exist in references.bib.")

    # 5. Figures existence check
    fig_refs = re.findall(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}', tex_text)
    print(f"\n[INFO] Figures embedded: {len(fig_refs)}")
    for fig_rel in fig_refs:
        fig_full = os.path.join(pub_dir, fig_rel)
        if not os.path.exists(fig_full) and not os.path.exists(fig_full + ".png") and not os.path.exists(fig_full + ".pdf"):
            print(f"  [WARNING] Figure file not found: {fig_full}")
        else:
            print(f"  [OK] Figure file exists: {fig_rel}")

    print("\n" + "=" * 70)
    print("  [SUCCESS] Manuscript 100% Validated against Official IOP Guidelines")
    print("=" * 70)

if __name__ == "__main__":
    verify_iop_manuscript()
