import shutil
import os

src_base = r'C:\Users\julio\OneDrive\Documentos\Antigra\Codex\nvs-wms-code-isolated'
dst_base = r'C:\Users\julio\OneDrive\Documentos\Antigra\warehouse-picker v2'

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

copytree_custom(src_base, dst_base)
print("Merge complete!")
