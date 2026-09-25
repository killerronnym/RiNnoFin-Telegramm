# 📋 Standard GitHub Release Workflow

To ensure seamless updates for the Synology NAS deployment, follow this procedure for every GitHub upload:

## 🚀 Quick Execution
Whenever the user says **"Lade es auf GitHub hoch"** or **"Lads auf Github hoch"**, run the following command:

```powershell
python scripts/publish_release.py "Kurze Zusammenfassung der Änderungen"
```

## 🔍 What the script does:
1.  **Version Increment:** Automatically updates `version.json` (e.g., v1.96 -> v1.97).
2.  **Commit & Push:** Runs `git commit -m "VERSION [vX.XX]: Summary"` and pushes to `main`.
3.  **Git Tagging:** Creates a local tag `vX.XX` and pushes it to GitHub.
4.  **GitHub Release:** Uses the **GitHub API Token** (from the DB settings) to create an official "Release" entry in the GitHub UI with title and description.
5.  **Verification:** Prints the URL of the new release.

## 🛠️ Requirements:
- The GitHub Personal Access Token must be set in the Dashboard (System Settings) or directly in the `bot_settings` table (`id_finder` config).
- Python library `requests` must be installed.

---
*Created on 2026-04-22*
