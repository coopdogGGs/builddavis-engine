#!/usr/bin/env python3
"""
BuildDavis GitHub Document Sync
================================
Pushes project documents to github.com/coopdogGGs/builddavis-world
Run from the folder where your documents are stored.

Usage:
    python push_docs.py

Requirements:
    pip install requests
"""

import os
import base64
import json
import requests

# ── CONFIG ────────────────────────────────────────────────────────────────────
GITHUB_USERNAME = "coopdogGGs"
REPO_NAME       = "builddavis-world"
GITHUB_API      = "https://api.github.com"

# Document mapping: local filename → GitHub path in repo
DOCUMENTS = {
    "ADR-001-BuildDavis-Architecture.docx":             "docs/adr/ADR-001-BuildDavis-Architecture.docx",
    "DATA-001-v2-BuildDavis-Data-Sources.docx":         "docs/data-sources/DATA-001-v2-BuildDavis-Data-Sources.docx",
    "SPEC-002-Build-Davis-Visual-Material-Classifier.docx": "docs/specs/SPEC-002-Build-Davis-Visual-Material-Classifier.docx",
}

# Commit message template
COMMIT_MESSAGE = "docs: update {filename}"

# ── TOKEN ─────────────────────────────────────────────────────────────────────
def get_token():
    """
    Reads your GitHub token from an environment variable or prompts you.
    Never hardcode the token in this file.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("\nNo GITHUB_TOKEN environment variable found.")
        print("You can set it permanently (see instructions below) or paste it now.\n")
        token = input("Paste your GitHub token: ").strip()
    return token

# ── GITHUB API HELPERS ────────────────────────────────────────────────────────
def get_headers(token):
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

def get_file_sha(token, repo_path):
    """Get the SHA of an existing file in the repo (needed to update it)."""
    url = f"{GITHUB_API}/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{repo_path}"
    r = requests.get(url, headers=get_headers(token))
    if r.status_code == 200:
        return r.json().get("sha")
    return None

def push_file(token, local_path, repo_path):
    """Push a single file to GitHub. Creates or updates as needed."""
    if not os.path.exists(local_path):
        print(f"  ✗ NOT FOUND locally: {local_path}")
        return False

    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    filename = os.path.basename(local_path)
    sha = get_file_sha(token, repo_path)

    payload = {
        "message": COMMIT_MESSAGE.format(filename=filename),
        "content": content,
    }
    if sha:
        payload["sha"] = sha  # Required for updates

    url = f"{GITHUB_API}/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{repo_path}"
    r = requests.put(url, headers=get_headers(token), data=json.dumps(payload))

    if r.status_code in (200, 201):
        action = "Updated" if sha else "Created"
        print(f"  ✓ {action}: {repo_path}")
        return True
    else:
        print(f"  ✗ Failed ({r.status_code}): {repo_path}")
        print(f"    {r.json().get('message', 'Unknown error')}")
        return False

def test_connection(token):
    """Verify the token works before attempting uploads."""
    r = requests.get(f"{GITHUB_API}/user", headers=get_headers(token))
    if r.status_code == 200:
        user = r.json()
        print(f"  ✓ Connected as: {user.get('login')} ({user.get('name', 'no name set')})")
        return True
    else:
        print(f"  ✗ Authentication failed ({r.status_code})")
        print("    Check your token has 'repo' scope and hasn't been revoked.")
        return False

def verify_repo(token):
    """Check the target repo exists and is accessible."""
    url = f"{GITHUB_API}/repos/{GITHUB_USERNAME}/{REPO_NAME}"
    r = requests.get(url, headers=get_headers(token))
    if r.status_code == 200:
        repo = r.json()
        visibility = "private" if repo.get("private") else "public"
        print(f"  ✓ Repo found: {repo.get('full_name')} ({visibility})")
        return True
    else:
        print(f"  ✗ Repo not found: {GITHUB_USERNAME}/{REPO_NAME}")
        return False

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  BuildDavis — GitHub Document Sync")
    print("=" * 55)

    # Get token
    token = get_token()
    if not token:
        print("\nNo token provided. Exiting.")
        return

    # Test connection
    print("\n[1/3] Testing connection...")
    if not test_connection(token):
        return

    # Verify repo
    print("\n[2/3] Checking repository...")
    if not verify_repo(token):
        return

    # Push documents
    print("\n[3/3] Pushing documents...")
    print(f"  Looking in: {os.getcwd()}\n")

    success = 0
    failed  = 0
    skipped = 0

    for local_filename, repo_path in DOCUMENTS.items():
        local_path = os.path.join(os.getcwd(), local_filename)
        if not os.path.exists(local_path):
            print(f"  - Skipped (not found): {local_filename}")
            skipped += 1
            continue
        result = push_file(token, local_path, repo_path)
        if result:
            success += 1
        else:
            failed += 1

    # Summary
    print("\n" + "=" * 55)
    print(f"  Done: {success} pushed · {failed} failed · {skipped} skipped")
    print(f"  Repo: https://github.com/{GITHUB_USERNAME}/{REPO_NAME}")
    print("=" * 55)

    if failed > 0:
        print("\n  Some files failed. Common causes:")
        print("  - Token missing 'repo' scope")
        print("  - Token has been revoked")
        print("  - File already up to date (no change)")

if __name__ == "__main__":
    main()
