"""Audit reference links for licensing compliance before sprite use.

Usage:
  python client/audit_reference_links.py "C:\\path\\to\\links.txt"

Accepted format per line:
  https://example.com/image.png | license: CC0
  https://example.com/model.glb | license: OWNED

Links without explicit permissive license markers are blocked.
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse


RE_URL = re.compile(r"(https?://\S+)")
PERMISSIVE_MARKERS = (
    "license: cc0",
    "license: public domain",
    "license: public-domain",
    "license: cc-by",
    "license: cc by",
    "license: mit",
    "license: apache-2.0",
    "license: owned",
    "license: own",
    "license: permission-granted",
    "license: permission granted",
)

LIKELY_COPYRIGHTED_DOMAINS = {
    "deviantart.com",
    "wixmp.com",
    "reddit.com",
    "redd.it",
    "mediafire.com",
    "sticknodes.com",
    "dreamstime.com",
    "vhv.rs",
    "mfgg.net",
    "ko-fi.com",
    "sketchfab.com",
    "turbosquid.com",
    "vrcmods.com",
    "meshy.ai",
    "ytimg.com",
    "youtube.com",
}


def has_permissive_marker(line_lower: str) -> bool:
    for marker in PERMISSIVE_MARKERS:
        if marker in line_lower:
            return True
    return False


def domain_of(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        return host[4:]
    return host


def classify_line(line: str) -> tuple[str, str, str]:
    match = RE_URL.search(line)
    if not match:
        return ("skip", "", "no_url_found")

    url = match.group(1).strip()
    line_lower = line.lower()
    domain = domain_of(url)

    if has_permissive_marker(line_lower):
        return ("approved", url, "explicit_permissive_license_marker")

    if domain in LIKELY_COPYRIGHTED_DOMAINS:
        return ("blocked", url, f"domain_requires_explicit_rights:{domain}")

    return ("blocked", url, "missing_explicit_permissive_license")


def audit_links_file(input_path: str, output_path: str) -> tuple[int, int, int]:
    approved: list[tuple[str, str]] = []
    blocked: list[tuple[str, str]] = []
    skipped = 0

    with open(input_path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line:
                continue

            status, url, reason = classify_line(line)
            if status == "approved":
                approved.append((url, reason))
            elif status == "blocked":
                blocked.append((url, reason))
            else:
                skipped += 1

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("Reference Link Compliance Report\n")
        out.write(f"Input: {input_path}\n\n")
        out.write(f"Approved: {len(approved)}\n")
        out.write(f"Blocked: {len(blocked)}\n")
        out.write(f"Skipped (non-URL lines): {skipped}\n\n")

        out.write("=== APPROVED (safe to use) ===\n")
        if approved:
            for url, reason in approved:
                out.write(f"- {url}\n  reason: {reason}\n")
        else:
            out.write("- none\n")

        out.write("\n=== BLOCKED (do not use) ===\n")
        if blocked:
            for url, reason in blocked:
                out.write(f"- {url}\n  reason: {reason}\n")
        else:
            out.write("- none\n")

        out.write("\nNext steps:\n")
        out.write("- Add explicit license marker per link, e.g. '| license: CC0'.\n")
        out.write("- Only links with permissive license markers are allowed for ingestion.\n")

    return (len(approved), len(blocked), skipped)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python client/audit_reference_links.py <links.txt> [output.txt]")
        return 1

    input_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets_boutique_fresh",
            "link_license_report.txt",
        )

    if not os.path.exists(input_path):
        print(f"Input not found: {input_path}")
        return 1

    approved_count, blocked_count, skipped_count = audit_links_file(input_path, output_path)
    print(f"Report written: {output_path}")
    print(f"approved={approved_count} blocked={blocked_count} skipped={skipped_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
