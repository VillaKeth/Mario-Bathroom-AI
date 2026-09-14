"""Run the headless wizard.js regression tests under pytest.

wizard.js is browser code with no JS test runner in this repo, so the suite
lives in tests/js/ and runs through Node. This wrapper surfaces it in the normal
pytest run and skips cleanly on machines without Node installed.
"""
import os
import shutil
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_TEST = os.path.join(REPO_ROOT, "tests", "js", "test_wizard_tags.js")


@pytest.mark.skipif(shutil.which("node") is None, reason="Node not installed")
def test_wizard_tag_persistence():
    """Tag inputs must not silently drop user input (accent markers, catchphrases)."""
    result = subprocess.run(
        ["node", JS_TEST],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"wizard.js tag tests failed:\n{result.stdout}\n{result.stderr}"
    )
    assert "0 failed" in result.stdout, result.stdout
