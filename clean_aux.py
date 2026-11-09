import os
import glob

exts = ["*.aux", "*.log", "*.fls", "*.fdb_latexmk", "*.out", "*.synctex.gz", "*.toc", "*.lot", "*.lof", "*.blg"]

count = 0
for ext in exts:
    for f in glob.glob(ext) + glob.glob(os.path.join("results", "publication", ext)):
        try:
            os.remove(f)
            count += 1
            print(f"Removed: {f}")
        except Exception as e:
            pass

print(f"\n[OK] Cleaned {count} auxiliary/cache files. Ready for fresh compilation!")
