import os
import re
import subprocess

def run_secret_audit():
    print("=" * 80)
    print("JANSAKSHI REPOSITORY SECRET & PII SCANNER")
    print("=" * 80)

    # Get list of files that git would track
    res = subprocess.run(["git", "status", "-s"], capture_output=True, text=True)
    untracked_lines = [line.strip() for line in res.stdout.splitlines() if line.startswith("??")]

    print(f"Checking {len(untracked_lines)} untracked entries...")

    # Regex patterns for sensitive data
    secret_patterns = {
        "Google Gemini API Key": r"AIzaSy[A-Za-z0-9_-]{33}",
        "Google OAuth Client Secret": r"GOCSPX-[A-Za-z0-9_-]{28}",
        "Generic Private Key": r"-----BEGIN (?:RSA )?PRIVATE KEY-----",
        "JWT Signature Token": r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        "AWS Secret Access Key": r"(?i)aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}",
    }

    # Get exact list of files that Git would track
    res_tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    res_untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True)

    git_files = set(res_tracked.stdout.splitlines() + res_untracked.stdout.splitlines())
    print(f"Git-visible file count: {len(git_files)}")

    # Ensure no forbidden files are in git_files
    for f in git_files:
        basename = os.path.basename(f)
        ext = os.path.splitext(f)[1].lower()
        if basename == ".env" or basename.endswith(".env") or basename.startswith(".env."):
            if basename != ".env.example":
                print(f"❌ CRITICAL ERROR: Git will track .env file: {f}")
                return False
        if ext in [".db", ".sqlite", ".sqlite3"] or "jansakshi.db" in f:
            print(f"❌ CRITICAL ERROR: Git will track database file: {f}")
            return False
        if "gmail_tokens" in f or "gmail_credentials" in f or "oauth_states" in f:
            print(f"❌ CRITICAL ERROR: Git will track OAuth token file: {f}")
            return False

    # Regex patterns for sensitive data
    secret_patterns = {
        "Google Gemini API Key": r"AIzaSy[A-Za-z0-9_-]{33}",
        "Google OAuth Client Secret": r"GOCSPX-[A-Za-z0-9_-]{28}",
        "Generic Private Key": r"-----BEGIN (?:RSA )?PRIVATE KEY-----",
        "JWT Signature Token": r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        "AWS Secret Access Key": r"(?i)aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}",
    }

    files_to_scan = []
    for f in git_files:
        ext = os.path.splitext(f)[1].lower()
        if ext in [".png", ".jpg", ".jpeg", ".mp4", ".ico", ".svg", ".docx"]:
            continue
        files_to_scan.append(f)

    print(f"Scanning {len(files_to_scan)} source & config files tracked by Git...")

    findings = []
    for filepath in files_to_scan:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for label, pat in secret_patterns.items():
                    matches = re.findall(pat, content)
                    if matches:
                        findings.append((filepath, label, len(matches)))
        except Exception as e:
            print(f"Warning: Could not read {filepath}: {e}")

    print("-" * 80)
    if findings:
        print(f"❌ FAILED! Found {len(findings)} potential secret pattern(s):")
        for fpath, label, count in findings:
            print(f"   - {fpath}: {label} ({count} match(es))")
        return False
    else:
        print("✅ PASSED: 0 secrets, API keys, or private tokens found in any source file!")
        print("=" * 80)
        return True

if __name__ == "__main__":
    success = run_secret_audit()
    if not success:
        exit(1)
