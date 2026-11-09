"""
Downloads and extracts the official IOP LaTeX template package from IOPscience.
Source URL: https://publishingsupport.iopscience.iop.org/wp-content/uploads/2025/07/ioplatextemplate.zip
"""

import os
import urllib.request
import zipfile

def download_and_extract():
    url = "https://publishingsupport.iopscience.iop.org/wp-content/uploads/2025/07/ioplatextemplate.zip"
    pub_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "publication")
    zip_path = os.path.join(pub_dir, "ioplatextemplate.zip")
    extract_dir = os.path.join(pub_dir, "iop_official_template")

    os.makedirs(pub_dir, exist_ok=True)
    os.makedirs(extract_dir, exist_ok=True)

    print(f"Downloading official IOP LaTeX template from:\n  {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    
    with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
        data = response.read()
        out_file.write(data)
    print(f"[OK] Downloaded {len(data)} bytes to {zip_path}")

    print(f"Extracting to {extract_dir} ...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        extracted_files = zip_ref.namelist()
    
    print(f"[OK] Extracted {len(extracted_files)} files:")
    for f in extracted_files:
        print(f"  - {f}")

if __name__ == "__main__":
    download_and_extract()
