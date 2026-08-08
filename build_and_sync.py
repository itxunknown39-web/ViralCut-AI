import subprocess
import shutil
import os
from pathlib import Path

ROOT_DIR = Path(r"e:\CLIPPING TOOL")
WEB_DIR = ROOT_DIR / "web"
DIST_DIR = WEB_DIR / "dist"
STATIC_DIR = ROOT_DIR / "static"

print("=" * 60)
print("🔨 BUILDING REACT FRONTEND (web/) AND SYNCING TO static/")
print("=" * 60)

# Run npm run build inside web/
try:
    print("Executing: npm run build in web/...")
    res = subprocess.run("npm run build", cwd=str(WEB_DIR), shell=True, capture_output=True, text=True)
    print("STDOUT:\n", res.stdout)
    print("STDERR:\n", res.stderr)
    if res.returncode != 0:
        print("❌ npm run build failed!")
    else:
        print("✅ npm run build succeeded!")
except Exception as e:
    print(f"❌ Exception running build: {e}")

# Sync DIST_DIR to STATIC_DIR
if DIST_DIR.exists():
    print("🔄 Synchronizing web/dist -> static/ ...")
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    
    # Copy index.html
    dist_html = DIST_DIR / "index.html"
    if dist_html.exists():
        shutil.copy2(dist_html, STATIC_DIR / "index.html")
        print("  Copied index.html -> static/index.html")
        
    # Copy assets/
    dist_assets = DIST_DIR / "assets"
    static_assets = STATIC_DIR / "assets"
    if dist_assets.exists():
        if static_assets.exists():
            shutil.rmtree(static_assets)
        shutil.copytree(dist_assets, static_assets)
        print("  Copied assets/ -> static/assets/")
        
    print("✅ Synchronization complete!")
else:
    print("⚠️ web/dist does not exist.")
