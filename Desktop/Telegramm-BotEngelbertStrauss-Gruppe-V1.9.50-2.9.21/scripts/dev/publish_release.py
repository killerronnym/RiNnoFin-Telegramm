#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import requests
from datetime import datetime

# Projekt-Root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)

from shared_bot_utils import get_bot_config

def run_git(args):
    print(f"Running: git {' '.join(args)}")
    result = subprocess.run(['git'] + args, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"Git Error: {result.stderr}")
        return False
    return True

def publish():
    print("\n--- STARTING STANDARD GITHUB RELEASE WORKFLOW ---\n")

    # 1. Version Increment
    version_file = os.path.join(PROJECT_ROOT, 'version.json')
    with open(version_file, 'r') as f:
        vdata = json.load(f)
    
    old_version = vdata['version']
    parts = old_version.split('.')
    parts[-1] = str(int(parts[-1]) + 1)
    new_version = ".".join(parts)
    
    vdata['version'] = new_version
    vdata['release_date'] = datetime.utcnow().isoformat() + "Z"
    
    with open(version_file, 'w') as f:
        json.dump(vdata, f, indent=4)
    
    print(f"DONE: Version incremented: {old_version} -> {new_version}")

    # 2. Commit & Push
    summary = sys.argv[1] if len(sys.argv) > 1 else f"Update to {new_version}"
    commit_msg = f"VERSION [v{new_version}]: {summary}"
    
    run_git(['add', 'version.json'])
    run_git(['add', '.']) 
    
    if not run_git(['commit', '-m', commit_msg]):
        print("INFO: Nothing to commit or git error. Continuing...")
    
    if not run_git(['push', 'origin', 'main']):
        print("ERROR: Could not push to main.")
        return

    print(f"DONE: Code pushed with message: {commit_msg}")

    # 3. Tag & Push Tag
    tag_name = f"v{new_version}"
    subprocess.run(['git', 'tag', '-d', tag_name], capture_output=True)
    
    if not run_git(['tag', tag_name]): return
    if not run_git(['push', 'origin', tag_name, '--force']): return
    print(f"DONE: Tag pushed: {tag_name}")

    # 4. Official GitHub Release via API
    # Suche Token in verschiedenen Configs (id_finder, system, etc.)
    token = None
    for bot_name in ['id_finder', 'system', 'invite']:
        config = get_bot_config(bot_name)
        if config.get('github_token') and 'your_pat' not in config['github_token']:
            token = config['github_token']
            owner = config.get('github_repo_owner', 'killerronnym')
            repo = config.get('github_repo_name', 'Telegramm-BotEngelbertStrauss-Gruppe-V1.9.50')
            print(f"INFO: Found GitHub token in '{bot_name}' settings.")
            break

    if not token:
        # Fallback to .env
        token = os.environ.get('GITHUB_TOKEN')
        owner = os.environ.get('GITHUB_REPO_OWNER', 'killerronnym')
        repo = os.environ.get('GITHUB_REPO_NAME', 'Telegramm-BotEngelbertStrauss-Gruppe-V1.9.50')
        if token and 'your_pat' not in token:
            print("INFO: Found GitHub token in .env file.")
        else:
            token = None

    if not token:
        print("ERROR: No valid GITHUB_TOKEN found in database settings or .env.")
        return

    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    payload = {
        "tag_name": tag_name,
        "target_commitish": "main",
        "name": f"{tag_name}: {summary}",
        "body": f"### Release {tag_name}\n\nAutomatisches Release vom System.\n\nÄnderungen: {summary}",
        "draft": False,
        "prerelease": False
    }

    print(f"API: Sending Release to GitHub API...")
    resp = requests.post(url, headers=headers, json=payload)
    
    if resp.status_code == 201:
        print(f"DONE: OFFICIAL RELEASE CREATED: {resp.json().get('html_url')}")
    else:
        print(f"ERROR API ({resp.status_code}): {resp.text}")

    print("\n--- WORKFLOW COMPLETED SUCCESSFULLY ---\n")

if __name__ == "__main__":
    publish()
