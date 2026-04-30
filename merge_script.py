import os
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
ANTIGRA_DIR = ROOT_DIR.parent
src_base = ANTIGRA_DIR / 'Codex' / 'nvs-wms-code-isolated'
dst_base = ROOT_DIR

ignores = {'node_modules', '.git', '__pycache__', '.claude', 'dist', '.ISOLADO', '.vscode'}

def copytree_custom(src, dst):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        if item in ignores: continue
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copytree_custom(s, d)
        else:
            try:
                shutil.copy2(s, d)
                print(f"Copied {d}")
            except Exception as e:
                print(f"Failed {s}: {e}")
copytree_custom(os.fspath(src_base), os.fspath(dst_base))
print("Merge complete!")
