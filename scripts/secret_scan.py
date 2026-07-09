#!/usr/bin/env python3
"""
Lightweight, dependency-free secret scanner used as the SECRETS check in the
compliance evidence pack. gitleaks/trufflehog aren't installable as pip
packages and their binaries aren't available in every build environment
(including this one), so rather than shipping a scan step that silently
degrades to a "NOT_INSTALLED" stub, this scans the working tree directly for
common committed-secret shapes: cloud provider keys, generic high-entropy
API tokens, and private key blocks. It is not a replacement for gitleaks on
a security team's toolchain, but it is a real, working check rather than a
placeholder.
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime, timezone

# (name, pattern, high_confidence) triples for recognizable secret shapes.
# High-confidence patterns match a specific real-world secret format (cloud
# provider keys, private key blocks, ...) and are checked everywhere. The
# generic "some_key = <opaque string>" pattern is intentionally lower
# confidence — it also matches test fixtures like api_key="test-secret" — so
# it is skipped under tests/, where such values are expected.
SECRET_PATTERNS = [
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}"), True),
    ("AWS Secret Access Key", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?"), True),
    ("Kaggle API Token", re.compile(r"KGAT_[0-9a-fA-F]{16,}"), True),
    ("Private Key Block", re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----"), True),
    ("Slack Token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"), True),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), True),
    ("Generic Bearer/API Token Assignment", re.compile(
        r"(?i)(api[_-]?key|api[_-]?token|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-./+]{16,}['\"]"
    ), False),
]

DEFAULT_EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".dvc", "mlruns", "data",
}

# Directories where low-confidence generic patterns are expected to produce
# false positives (test fixtures, mock credentials) and are skipped.
LOW_CONFIDENCE_EXEMPT_DIRS = {"tests"}

# Placeholder values that legitimately appear in tracked template files
# (e.g. .env.example) and should not be flagged.
PLACEHOLDER_SUBSTRINGS = ("REPLACE_WITH", "YOUR_", "EXAMPLE", "xxxxxxxx", "changeme")


def scan_repo_for_secrets(repo_root: str, exclude_dirs: set | None = None) -> list[dict]:
    exclude_dirs = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    findings = []

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        rel_dir = os.path.relpath(root, repo_root)
        in_exempt_dir = rel_dir.split(os.sep)[0] in LOW_CONFIDENCE_EXEMPT_DIRS

        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        if any(ph in line for ph in PLACEHOLDER_SUBSTRINGS):
                            continue
                        for rule_name, pattern, high_confidence in SECRET_PATTERNS:
                            if not high_confidence and in_exempt_dir:
                                continue
                            match = pattern.search(line)
                            if match:
                                findings.append({
                                    "rule": rule_name,
                                    "file": os.path.relpath(filepath, repo_root),
                                    "line": line_num,
                                    "match_preview": match.group(0)[:12] + "...",
                                })
            except (UnicodeDecodeError, PermissionError, OSError):
                continue

    return findings


def run_scan(repo_root: str, report_path: str) -> int:
    findings = scan_repo_for_secrets(repo_root)
    report = {
        "scanner": "ARGUS built-in secret scanner (scripts/secret_scan.py)",
        "status": "FINDINGS" if findings else "CLEAN",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "findings_count": len(findings),
        "findings": findings,
        "note": "Regex-based scan over the working tree (git history not scanned). "
        "Not a substitute for gitleaks/trufflehog in a full security pipeline.",
    }
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return 1 if findings else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARGUS built-in secret scanner")
    parser.add_argument("--repo-root", type=str, default=".")
    parser.add_argument("--report-path", type=str, default="secret_scan_report.json")
    args = parser.parse_args()

    exit_code = run_scan(args.repo_root, args.report_path)
    sys.exit(exit_code)
