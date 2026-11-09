import os
import subprocess
import fitz

def test_compile():
    tex_file = "manuscript_bioinspiration.tex"
    cmd = r'"C:\Users\potiwatnga\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe" -interaction=nonstopmode manuscript_bioinspiration.tex'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=r"e:\agy\snake - Copy")
    print(f"pdflatex returncode: {res.returncode}")
    doc = fitz.open(r"e:\agy\snake - Copy\manuscript_bioinspiration.pdf")
    print(f"Total pages: {len(doc)}")
    for i, page in enumerate(doc):
        txt = page.get_text().strip()
        print(f"Page {i+1}: {len(txt)} chars | First: {txt.splitlines()[0][:30] if txt else 'EMPTY'} | Last: {txt.splitlines()[-1][-30:] if txt else 'EMPTY'}")

if __name__ == "__main__":
    test_compile()
