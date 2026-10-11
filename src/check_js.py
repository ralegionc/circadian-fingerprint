"""Extract each <script> block from site/index.html and syntax-check it with node."""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "site", "index.html")

html = open(INDEX, encoding="utf-8").read()
blocks = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
print(f"{len(blocks)} script blocks")

fail = False
for i, src in enumerate(blocks, 1):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(src)
        path = fh.name
    res = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    label = f"block {i} ({len(src)//1024} KB)"
    if res.returncode:
        fail = True
        print(f"  {label}: FAIL\n{res.stderr.strip()[:900]}")
    else:
        print(f"  {label}: ok")
    os.unlink(path)

sys.exit(1 if fail else 0)
