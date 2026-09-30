# Demo walkthrough: docforge Console

A 10-minute demo that shows the whole loop. It costs nothing unless you choose a live run. All commands run in the Ubuntu (WSL) terminal.

## Before the demo

1. Start Docker Desktop and open Ubuntu (`wsl -d Ubuntu-24.04 -u allti`). The OpenShell gateway starts with Ubuntu.
2. Start the console from the docforge checkout:
   ```bash
   cd /mnt/c/Users/allti/OneDrive/Documents/nvidia_openshell_agent
   ./dev.sh docforge serve
   ```
3. Open the printed `http://127.0.0.1:8765/auth?t=…` link in your browser. Without that link the console shows "Session needed".
4. On **Repos**, add `/home/allti/pilot-live` and this folder's full path.

## The story, screen by screen

1. **Repos.** Each repository's docs health, computed by the same checks as `docforge check`: errors, warnings, drift (code changed without docs) and "uncertain" items waiting for the developer.
2. **Repo detail** (select `pilot-live`). Coverage per document, the 8 decision records the agent wrote, and the check results.
3. **Agent runs → Play replay** on *First documentation pass on markdown-visualiser*. Watch the recorded run: each teal line is a model turn with its cost, and the others are tool calls made through docforge's policy layer inside the sandbox. It cost $1.40 when it really ran; the replay costs $0.
4. **Review.** The agent's report (with the discrepancies it found in the code, such as the unused `printSchema`) next to the patch as a diff. Replays show that there is nothing to publish.
5. **Manual.** Build the PDF and preview it in the page.
6. **Security → Replay recorded run.** All 8 attacks blocked: the key never enters the sandbox, other hosts are refused, system paths are read-only, and the PDF builds with no network.
7. **Usage.** Real spend against the monthly cap.

## Optional: a live run (spends API credit)

On a repository page, select **Run agent**, choose **Live** and **impact**. It costs about $0.04–0.25, capped at $0.50. When it finishes:

1. **Review** the report and diff.
2. **Apply patch** creates a `docforge/impact-…` branch with only doc changes.
3. **Push branch** shows the remote, branch, commits and files, then pushes with your GitHub login.
4. **Open pull request** uses the agent's report as the description. Merge it on GitHub; the console never merges.

For a free live demo, choose **Security → Run live** instead. It creates two real sandboxes and runs every attack (the only model call is to a free endpoint).

## If something goes wrong

- **"Session needed":** open the exact link printed by `docforge serve`; it changes each start.
- **Live run unavailable:** start the console from the docforge checkout, so it can find `sandbox/`.
- **Sandboxes fail to start:** see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and `openshell status`.
