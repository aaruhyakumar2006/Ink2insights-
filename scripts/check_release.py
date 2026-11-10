#!/usr/bin/env python3
"""Release Safety & Secret Leakage Scanner.

Scans release artifacts, repositories, or zip packages to ensure:
- Zero .env files (only .env.example with empty values is allowed)
- Zero *.db, *.sqlite, *.sqlite3 database files
- Zero leaked API keys (OpenAI, Anthropic, Gemini, NVIDIA, Groq)
- Zero Supabase service_role keys or secrets
- Zero JWT tokens (eyJ...)
- Zero unmasked real patient personal identifiers (e.g. 12-digit Aadhaar)

Usage:
    python scripts/check_release.py
    python scripts/check_release.py --target ./dist_folder
    python scripts/check_release.py --zip ./release.zip
"""

import os
import sys
import re
import zipfile
import argparse
from typing import List, Tuple, Dict, Any

# Forbidden filename patterns
FORBIDDEN_FILE_PATTERNS = [
    r"^\.env$",
    r"^\.env\.(?!example$)[a-zA-Z0-9_\.]+$",
    r"\.db$",
    r"\.sqlite$",
    r"\.sqlite3$",
    r"\.pem$",
    r"\.key$",
    r"^id_rsa.*",
    r"^data[\\/].*",
    r"^private_uploads[\\/].*",
    r"^frontend[\\/]uploads[\\/].*",
]

# Forbidden content regex patterns
FORBIDDEN_CONTENT_PATTERNS = [
    (r"service_role", "Supabase service_role key reference or token"),
    (r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", "Live JWT token (eyJ...)"),
    (r"sk-ant-[a-zA-Z0-9_\-]{20,}", "Anthropic Claude API key"),
    (r"nvapi-[a-zA-Z0-9_\-]{20,}", "NVIDIA NIM API key"),
    (r"AIzaSy[a-zA-Z0-9_\-]{30,}", "Google Gemini / Firebase API key"),
    (r"gsk_[a-zA-Z0-9_\-]{20,}", "Groq Vision API key"),
    (r"sk-[a-zA-Z0-9]{32,}", "OpenAI API key"),
    (r"\b[2-9]{1}\d{3}\s\d{4}\s\d{4}\b", "Indian Aadhaar personal identification number"),
]

# Allowed files that may mention patterns in documentation or code definitions
WHITELISTED_FILES = {
    ".gitignore",
    ".env.example",
    "check_release.py",
    "test_v1_task3_security_hardening.py",
    "test_v1_task3.py",
    "test_api.py",
    "test_ai_service.py",
    "auth_service.py",
    "test_v1_task4_roles_and_fixes.py",
    "test_v1_task9_task10.py",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "data",
    "private_uploads",
}

# Standard recommended ZIP package excludes
ZIP_EXCLUDE_ARGS = [
    "-x",
    "*.git*",
    "*__pycache__*",
    "*.pytest_cache*",
    "*.venv*",
    "*venv*",
    "*.env*",
    "!*.env.example",
    "*.db*",
    "*.sqlite*",
    "data/*",
    "private_uploads/*",
    "frontend/uploads/*",
    "*.jpg",
    "*.jpeg",
    "*.png",
]


def load_gitignore_patterns(root_dir: str) -> List[str]:
    """Parse .gitignore from project root."""
    gitignore_path = os.path.join(root_dir, ".gitignore")
    patterns = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                l = line.strip()
                if l and not l.startswith("#"):
                    patterns.append(l)
    return patterns


def is_ignored(rel_path: str, gitignore_patterns: List[str]) -> bool:
    """Check if relative path matches common gitignore patterns."""
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts:
        if part in IGNORED_DIRECTORIES:
            return True

    clean_rel = rel_path.replace("\\", "/")
    for pat in gitignore_patterns:
        clean_pat = pat.rstrip("/").replace("\\", "/")
        if clean_rel == clean_pat or clean_rel.startswith(clean_pat + "/"):
            return True
        if clean_pat.startswith("*.") and clean_rel.endswith(clean_pat[1:]):
            return True
        if clean_pat == ".env" and os.path.basename(clean_rel) == ".env":
            return True
    return False


def scan_file_content(file_path: str, rel_path: str) -> List[Tuple[str, str, int, str]]:
    """Scan file content for forbidden tokens and real patient data."""
    base_name = os.path.basename(file_path)
    if base_name in WHITELISTED_FILES or rel_path in WHITELISTED_FILES:
        return []

    # Skip large binary files
    try:
        with open(file_path, "rb") as f:
            sample = f.read(4096)
            if b"\x00" in sample:
                return []
    except Exception:
        return []

    violations = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                for regex, desc in FORBIDDEN_CONTENT_PATTERNS:
                    if re.search(regex, line):
                        # Skip placeholder mock comments in tests
                        if "test" in rel_path.lower() and "TEST_JWT" in line:
                            continue
                        snippet = line.strip()[:100]
                        violations.append((rel_path, desc, line_no, snippet))
    except Exception as e:
        violations.append((rel_path, f"Could not read file: {e}", 0, ""))

    return violations


def scan_directory(target_dir: str, root_dir: str) -> List[str]:
    """Scan a target folder for release safety violations."""
    violations = []
    gitignore_patterns = load_gitignore_patterns(root_dir)

    for root, dirs, files in os.walk(target_dir):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES]

        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, target_dir)

            # Check filename against forbidden patterns
            for pat in FORBIDDEN_FILE_PATTERNS:
                if re.search(pat, file, re.IGNORECASE):
                    # Check if ignored by .gitignore (if scanning unzipped workspace)
                    if not is_ignored(rel_path, gitignore_patterns):
                        violations.append(f"[FORBIDDEN FILE] {rel_path} matches forbidden pattern '{pat}'")

            # Check file content
            if not is_ignored(rel_path, gitignore_patterns):
                content_violations = scan_file_content(full_path, rel_path)
                for f_rel, desc, line_no, snippet in content_violations:
                    violations.append(f"[LEAK DETECTED] {f_rel}:{line_no} - {desc} -> {snippet}")

    return violations


def scan_zip(zip_path: str) -> List[str]:
    """Scan the inside of a zip archive without extracting."""
    violations = []
    if not os.path.exists(zip_path):
        return [f"Zip archive '{zip_path}' does not exist."]

    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            filename = os.path.basename(info.filename)
            rel_path = info.filename

            # Forbidden filename
            for pat in FORBIDDEN_FILE_PATTERNS:
                if re.search(pat, filename, re.IGNORECASE):
                    violations.append(f"[FORBIDDEN FILE IN ZIP] {rel_path} matches '{pat}'")

            # Forbidden content
            if not info.is_dir() and filename not in WHITELISTED_FILES:
                try:
                    with z.open(info) as f:
                        sample = f.read(4096)
                        if b"\x00" not in sample:
                            f.seek(0)
                            content = f.read().decode("utf-8", errors="ignore")
                            for line_no, line in enumerate(content.splitlines(), start=1):
                                for regex, desc in FORBIDDEN_CONTENT_PATTERNS:
                                    if re.search(regex, line):
                                        violations.append(f"[LEAK IN ZIP] {rel_path}:{line_no} - {desc}")
                except Exception as e:
                    violations.append(f"[ZIP READ ERROR] Could not inspect {rel_path}: {e}")

    return violations


def main():
    parser = argparse.ArgumentParser(description="Check release artifacts for secrets, .env, DBs, and patient data.")
    parser.add_argument("--target", default=None, help="Directory to scan (default: project root)")
    parser.add_argument("--zip", dest="zip_path", default=None, help="Zip archive to scan")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    scan_target = os.path.abspath(args.target) if args.target else project_root

    print("=" * 65)
    print("  I2 insights — Release Artifact Safety Scanner")
    print("=" * 65)

    if args.zip_path:
        print(f"Scanning Zip Archive: {args.zip_path}")
        violations = scan_zip(args.zip_path)
    else:
        print(f"Scanning Directory: {scan_target}")
        violations = scan_directory(scan_target, project_root)

    if violations:
        print(f"\n[FAIL] Found {len(violations)} security violation(s):")
        for v in violations:
            print(f"  * {v}")
        print("\nFix these violations before releasing or packaging!")
        sys.exit(1)
    else:
        print("\n[PASS] Zero forbidden files, zero leaked keys, zero JWTs, and zero unmasked patient data found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
