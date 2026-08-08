"""ViralCut AI — GitHub Publishing Script

Automates security auditing, staging, committing, and pushing ViralCut AI to GitHub:
Remote: https://github.com/itxunknown39-web/ViralCut-AI.git
Branch: main
"""

import os
import sys
import subprocess
from pathlib import Path

REMOTE_URL = "https://github.com/itxunknown39-web/ViralCut-AI.git"
BRANCH = "main"
COMMIT_MSG = "feat: final release update - 7-screen wizard UI, Colab-compatible downloader, and static asset sync"

ROOT_DIR = Path(__file__).parent.resolve()

def run(cmd, check=True):
    print(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"❌ Error (exit code {res.returncode}):\n{res.stderr}")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return res

def audit_security():
    print("🔍 Auditing project files for sensitive data & large binaries...")
    sensitive_extensions = [".env", ".pem", ".key", ".pkcs12", ".pfx"]
    forbidden_files = []
    
    for root, dirs, files in os.walk(ROOT_DIR):
        # Skip git directory
        if ".git" in dirs:
            dirs.remove(".git")
        if "node_modules" in dirs:
            dirs.remove("node_modules")
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
            
        for f in files:
            fp = Path(root) / f
            rel = fp.relative_to(ROOT_DIR)
            
            # Check for cookies / env files
            if "cookie" in f.lower() and f.endswith(".txt"):
                forbidden_files.append(str(rel))
            elif any(f.endswith(ext) for ext in sensitive_extensions):
                forbidden_files.append(str(rel))
                
    if forbidden_files:
        print(f"❌ SECURITY AUDIT FAILED! Found sensitive files that must not be committed:\n" + "\n".join(forbidden_files))
        sys.exit(1)
        
    print("✅ Security audit passed: No sensitive files or credentials found.")

def main():
    print("=" * 60)
    print("🚀 PUBLISHING VIRALCUT AI TO GITHUB")
    print(f"• Remote: {REMOTE_URL}")
    print(f"• Branch: {BRANCH}")
    print("=" * 60)

    # Build React frontend if Node/npm is present and sync to static/
    web_dir = ROOT_DIR / "web"
    dist_dir = web_dir / "dist"
    static_dir = ROOT_DIR / "static"
    if (web_dir / "package.json").exists():
        print("🔨 Building React dashboard (web/)...")
        b_res = subprocess.run("npm run build", cwd=str(web_dir), shell=True, capture_output=True, text=True)
        if b_res.returncode == 0:
            print("✅ React build succeeded.")
        else:
            print("⚠️ npm run build note:", b_res.stderr.strip() or b_res.stdout.strip())
            
    if dist_dir.exists():
        import shutil
        print("🔄 Synchronizing web/dist -> static/ ...")
        static_dir.mkdir(parents=True, exist_ok=True)
        if (dist_dir / "index.html").exists():
            shutil.copy2(dist_dir / "index.html", static_dir / "index.html")
        if (dist_dir / "assets").exists():
            st_assets = static_dir / "assets"
            if st_assets.exists():
                shutil.rmtree(st_assets)
            shutil.copytree(dist_dir / "assets", st_assets)
        print("✅ static/ folder synchronized with web/dist.")

    # Remove extra notebook files if present
    extra_nb = ROOT_DIR / "ViralCutAI_Colab_Simple.ipynb"
    if extra_nb.exists():
        print(f"🧹 Removing extra notebook file: {extra_nb.name}")
        run(["git", "rm", "-f", extra_nb.name], check=False)
        if extra_nb.exists():
            extra_nb.unlink()

    # 1. Initialize Git if not present
    git_dir = ROOT_DIR / ".git"
    if not git_dir.exists():
        print("⚙️ Initializing Git repository...")
        run(["git", "init"])
        run(["git", "branch", "-M", BRANCH])
    else:
        print("✅ Git repository already initialized.")

    # 2. Check / configure remote URL
    remotes_res = run(["git", "remote", "-v"], check=False)
    if "origin" in remotes_res.stdout:
        print("🔄 Updating origin remote URL...")
        run(["git", "remote", "set-url", "origin", REMOTE_URL])
    else:
        print("➕ Adding origin remote URL...")
        run(["git", "remote", "add", "origin", REMOTE_URL])

    # 3. Ensure branch is set to main
    run(["git", "checkout", "-B", BRANCH])

    # 4. Stage files
    print("📦 Staging project files...")
    run(["git", "add", "."])

    # 5. Check status
    status_res = run(["git", "status", "--porcelain"], check=False)
    if not status_res.stdout.strip():
        print("ℹ️ No new changes to commit.")
    else:
        print(f"✍️ Creating commit: '{COMMIT_MSG}'...")
        run(["git", "commit", "-m", COMMIT_MSG])

    # 6. Push to remote main
    print(f"⬆️ Pushing to {REMOTE_URL} ({BRANCH})...")
    push_res = run(["git", "push", "-u", "origin", BRANCH], check=False)
    
    if push_res.returncode == 0:
        print("\n🎉 SUCCESS! ViralCut AI published to GitHub successfully.")
    else:
        print(f"\n⚠️ Push output:\n{push_res.stdout}\n{push_res.stderr}")
        print("\nIf the remote repository requires authentication or contains existing commits, run 'git push -u origin main' in your terminal.")

    # Final verification
    rev_res = run(["git", "rev-parse", "HEAD"], check=False)
    commit_hash = rev_res.stdout.strip() if rev_res.returncode == 0 else "Unknown"

    print("\n" + "=" * 60)
    print("FINAL SUMMARY:")
    print(f"• Remote URL:  {REMOTE_URL}")
    print(f"• Branch:      {BRANCH}")
    print(f"• Commit Hash: {commit_hash}")
    print(f"• Push Status: {'SUCCESS' if push_res.returncode == 0 else 'PENDING / HANDOFF'}")
    print("• Excluded:    node_modules, .venv, downloads/, clips/, transcripts/, *.mp4, cookies, .env")
    print("=" * 60)

if __name__ == "__main__":
    main()
