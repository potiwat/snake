import shutil
from pathlib import Path

root = Path(".")
pub = Path("results/publication")

# 1. Sync tex and bib
shutil.copy(pub / "manuscript_bioinspiration.tex", root / "manuscript_bioinspiration.tex")
shutil.copy(pub / "manuscript_bioinspiration.tex", root / "manuscript.tex")
shutil.copy(pub / "references.bib", root / "references.bib")

# 2. Sync cls, bst, orcid
shutil.copy(pub / "iopjournal.cls", root / "iopjournal.cls")
shutil.copy(pub / "orcid.pdf", root / "orcid.pdf")
if (pub / "iopart-num.bst").exists():
    shutil.copy(pub / "iopart-num.bst", root / "iopart-num.bst")

# 3. Sync figures folder to root
root_fig = root / "figures"
root_fig.mkdir(exist_ok=True)
count = 0
for fig in (pub / "figures").glob("*.*"):
    shutil.copy(fig, root_fig / fig.name)
    count += 1

print(f"[OK] Synchronized all assets to root workspace directory ({count} figures synced).")
