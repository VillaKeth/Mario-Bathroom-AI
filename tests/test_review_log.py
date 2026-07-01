# tests/test_review_log.py
import datetime, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import review_log


def test_resolve_and_read(tmp_path, capsys):
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    d = tmp_path / day
    d.mkdir(parents=True)
    (d / "conversation.log").write_text(
        "2026-07-01@10:00:00.000  [guest] hi\n"
        "2026-07-01@10:00:01.000  [rudi] hello\n"
        "2026-07-01@10:00:02.000  [guest] bye\n", encoding="utf-8")
    p = review_log.resolve_log_path(str(tmp_path), None, "conversation")
    assert p.endswith(os.path.join(day, "conversation.log"))
    review_log.main(["--root", str(tmp_path), "--grep", "guest"])
    out = capsys.readouterr().out
    assert "[guest] hi" in out and "[guest] bye" in out and "[rudi] hello" not in out
