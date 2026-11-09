import re
from pathlib import Path

script_path = Path("analysis/generate_iop_latex_manuscript.py")
code = script_path.read_text(encoding="utf-8")

# Extract BIBTEX_CONTENT and LATEX_MANUSCRIPT_CONTENT
m_bib = re.search(r'BIBTEX_CONTENT = r"""(.*?)"""', code, re.DOTALL)
m_tex = re.search(r'LATEX_MANUSCRIPT_CONTENT = r"""(.*?)"""', code, re.DOTALL)

bib_text = m_bib.group(1)
tex_text = m_tex.group(1)

# Step 1: Initial first appearance order
cites = re.findall(r'\\cite\{([^}]+)\}', tex_text)
first_seen = {}
for c in cites:
    for k in c.split(','):
        k = k.strip()
        if k not in first_seen:
            first_seen[k] = len(first_seen) + 1

# Step 2: Sort in-text multi-citations without space
def sort_cite(match):
    content = match.group(1)
    keys = [k.strip() for k in content.split(',') if k.strip()]
    sorted_keys = sorted(keys, key=lambda k: first_seen.get(k, 999))
    return r'\cite{' + ','.join(sorted_keys) + '}'

new_tex_text = re.sub(r'\\cite\{([^}]+)\}', sort_cite, tex_text)

# Step 3: Re-compute exact appearance order
cites2 = re.findall(r'\\cite\{([^}]+)\}', new_tex_text)
order = []
for c in cites2:
    for k in c.split(','):
        k = k.strip()
        if k not in order:
            order.append(k)

# Step 4: Parse all bib entries robustly
entries = re.findall(r'@(\w+)\s*\{\s*([^,]+),\s*(.*?)\n\}', bib_text, re.DOTALL)
bib_dict = {}
for entry_type, key, body in entries:
    key_clean = key.strip()
    bib_dict[key_clean] = f"@{entry_type}{{{key_clean},\n{body.strip()}\n}}"

# Build sorted bib text
sorted_bib_list = []
for idx, k in enumerate(order, 1):
    entry = bib_dict[k]
    sorted_bib_list.append(f'% [{idx:2d}] First cited in text (Citation #{idx})\n{entry}')

new_bib_text = '\n\n'.join(sorted_bib_list) + '\n'

# Replace in code
new_code = code[:m_bib.start(1)] + new_bib_text + code[m_bib.end(1):m_tex.start(1)] + new_tex_text + code[m_tex.end(1):]

script_path.write_text(new_code, encoding="utf-8")
print(f"[OK] Successfully sorted all {len(order)} citations and re-ordered references.bib!")
