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


def test_tail_returns_last_n(tmp_path, capsys):
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    d = tmp_path / day; d.mkdir(parents=True)
    (d / "conversation.log").write_text("l1\nl2\nl3\nl4\nl5\n", encoding="utf-8")
    review_log.main(["--root", str(tmp_path), "--tail", "2"])
    assert capsys.readouterr().out == "l4\nl5\n"


def test_tail_zero_returns_nothing(tmp_path, capsys):
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    d = tmp_path / day; d.mkdir(parents=True)
    (d / "conversation.log").write_text("l1\nl2\n", encoding="utf-8")
    review_log.main(["--root", str(tmp_path), "--tail", "0"])
    assert capsys.readouterr().out == ""


def test_grep_case_insensitive_mixed(tmp_path, capsys):
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    d = tmp_path / day; d.mkdir(parents=True)
    (d / "conversation.log").write_text("A  [guest] HELLO there\nB  [rudi] bye\n", encoding="utf-8")
    review_log.main(["--root", str(tmp_path), "--grep", "hello"])  # lowercase term vs UPPERCASE content
    out = capsys.readouterr().out
    assert "HELLO there" in out and "bye" not in out


def test_missing_log_message_to_stderr(tmp_path, capsys):
    review_log.main(["--root", str(tmp_path), "--day", "1999-01-01"])
    cap = capsys.readouterr()
    assert cap.out == ""
    assert "no log at" in cap.err
