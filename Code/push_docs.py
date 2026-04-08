"""
BuildDavis — GitHub Document & Code Sync
Pushes all project files to github.com/coopdogGGs/builddavis-world
Run: python push_docs.py
"""

import os
import sys
import base64
import hashlib
import requests

GITHUB_OWNER = "coopdogGGs"
GITHUB_REPO  = "builddavis-world"
API_BASE     = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"

# Where your files live locally
DOCS_FOLDER = os.path.expanduser(r"REDACTED_PATH\Downloads")
CODE_FOLDER = os.path.expanduser(r"REDACTED_PATH\Downloads")

# ── Files to push ─────────────────────────────────────────────────────────────
# Format: (local_filename, github_path, folder_variable)
FILES = [
    # Documents
    ("ADR-001-BuildDavis-Architecture.docx",                "docs/adr/ADR-001-BuildDavis-Architecture.docx",                    DOCS_FOLDER),
    ("ADR-002-BuildDavis-Pipeline-Architecture.docx",       "docs/adr/ADR-002-BuildDavis-Pipeline-Architecture.docx",           DOCS_FOLDER),
    ("DATA-001-v3-BuildDavis-Data-Sources.docx",            "docs/data-sources/DATA-001-v3-BuildDavis-Data-Sources.docx",       DOCS_FOLDER),
    ("SPEC-001-BuildDavis-LiDAR-Terrain-Pipeline.docx",     "docs/specs/SPEC-001-BuildDavis-LiDAR-Terrain-Pipeline.docx",       DOCS_FOLDER),
    ("SPEC-002-Build-Davis-Visual-Material-Classifier.docx","docs/specs/SPEC-002-Build-Davis-Visual-Material-Classifier.docx",  DOCS_FOLDER),
    ("SPEC-003-BuildDavis-Block-Palette.docx",              "docs/specs/SPEC-003-BuildDavis-Block-Palette.docx",                DOCS_FOLDER),
    ("ICONIC-001-BuildDavis-Iconic-Brief.docx",             "docs/landmarks/ICONIC-001-BuildDavis-Iconic-Brief.docx",           DOCS_FOLDER),
    ("PROJECT-BRIEF-BuildDavis.docx",                       "docs/PROJECT-BRIEF-BuildDavis.docx",                               DOCS_FOLDER),
    # Updated docs — session 2
    ("ADR-002-BuildDavis-Pipeline-Architecture.docx",       "docs/adr/ADR-002-BuildDavis-Pipeline-Architecture.docx",          DOCS_FOLDER),
    ("ICONIC-001-BuildDavis-Iconic-Brief.docx",             "docs/landmarks/ICONIC-001-BuildDavis-Iconic-Brief.docx",           DOCS_FOLDER),
    # New docs — session 2
    ("SPEC-004-BuildDavis-Region-Protection.docx",          "docs/specs/SPEC-004-BuildDavis-Region-Protection.docx",            DOCS_FOLDER),
    ("ADR-003-BuildDavis-Regen-Policy.docx",                "docs/adr/ADR-003-BuildDavis-Regen-Policy.docx",                   DOCS_FOLDER),
    ("AGENT-001-BuildDavis-Agent-Roles.docx",               "docs/AGENT-001-BuildDavis-Agent-Roles.docx",                      DOCS_FOLDER),
    ("VISION-001-BuildDavis-Live-Service.docx",             "docs/VISION-001-BuildDavis-Live-Service.docx",                    DOCS_FOLDER),
    # Source code
    ("fetch.py",                                            "src/builddavis/fetch.py",                                          CODE_FOLDER),
    ("lidar.py",                                            "src/builddavis/lidar.py",                                          CODE_FOLDER),
    ("parse.py",                                            "src/builddavis/parse.py",                                          CODE_FOLDER),
    ("fuse.py",                                             "src/builddavis/fuse.py",                                           CODE_FOLDER),
    ("transform.py",                                        "src/builddavis/transform.py",                                      CODE_FOLDER),
]


def get_token():
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    print("\nNo GITHUB_TOKEN environment variable found.")
    print("You can set it permanently (see instructions below) or paste it now.")
    token = input("Paste your GitHub token: ").strip()
    if not token:
        print("No token provided. Exiting.")
        sys.exit(1)
    return token


def get_file_sha(path: str, headers: dict) -> str | None:
    """Get the current SHA of a file in GitHub (needed for updates)."""
    resp = requests.get(f"{API_BASE}/contents/{path}", headers=headers)
    if resp.status_code == 200:
        return resp.json().get("sha")
    return None


def push_file(local_path: str, github_path: str, headers: dict) -> str:
    """Push a single file. Returns 'created', 'updated', or 'skipped'."""
    if not os.path.exists(local_path):
        return "not_found"

    with open(local_path, "rb") as f:
        content = f.read()
    encoded = base64.b64encode(content).decode()

    sha = get_file_sha(github_path, headers)
    filename = os.path.basename(local_path)

    if sha:
        # Check if content actually changed (avoid unnecessary commits)
        resp = requests.get(f"{API_BASE}/contents/{github_path}", headers=headers)
        if resp.status_code == 200:
            remote_b64 = resp.json().get("content", "").replace("\n", "")
            if remote_b64 == encoded:
                return "unchanged"

    payload = {
        "message": f"{'Update' if sha else 'Add'} {filename}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(f"{API_BASE}/contents/{github_path}", headers=headers, json=payload)
    if resp.status_code in (200, 201):
        return "updated" if sha else "created"
    else:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text[:200]}")


def main():
    print("=" * 55)
    print("  BuildDavis — GitHub Sync")
    print("=" * 55)

    token = get_token()
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Verify connection
    print("\n[1/3] Testing connection...")
    resp = requests.get("https://api.github.com/user", headers=headers)
    if resp.status_code != 200:
        print(f"  ERROR: Could not authenticate. Status {resp.status_code}")
        sys.exit(1)
    user = resp.json()
    print(f"  Connected as: {user['login']} ({user.get('name', '')})")

    # Verify repo
    print("\n[2/3] Checking repository...")
    resp = requests.get(API_BASE, headers=headers)
    if resp.status_code != 200:
        print(f"  ERROR: Repo not found. Status {resp.status_code}")
        sys.exit(1)
    repo = resp.json()
    visibility = "private" if repo.get("private") else "public"
    print(f"  Repo found: {repo['full_name']} ({visibility})")

    # Push files
    print("\n[3/3] Pushing files...")
    created = updated = skipped = failed = 0

    for filename, github_path, folder in FILES:
        local_path = os.path.join(folder, filename)
        try:
            result = push_file(local_path, github_path, headers)
            if result == "not_found":
                print(f"  - Skipped (not found): {filename}")
                skipped += 1
            elif result == "unchanged":
                print(f"  = Unchanged: {filename}")
                skipped += 1
            elif result == "created":
                print(f"  + Created:  {github_path}")
                created += 1
            elif result == "updated":
                print(f"  ~ Updated:  {github_path}")
                updated += 1
        except Exception as e:
            print(f"  ERROR pushing {filename}: {e}")
            failed += 1

    print("\n" + "=" * 55)
    total_pushed = created + updated
    print(f"  Done: {total_pushed} pushed ({created} new, {updated} updated)")
    print(f"        {skipped} unchanged/skipped  |  {failed} failed")
    print(f"  Repo: https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}")
    print("=" * 55)

    if failed:
        print(f"\n  WARNING: {failed} file(s) failed to push. Check errors above.")


if __name__ == "__main__":
    main()
