import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from character_creator import voice_finetune as vf


def test_parse_status_reads_epoch_and_stage():
    log = "INFO:pomni:start training\nINFO:pomni:====> Epoch: 3\nsome s2 line\n"
    st = vf.parse_training_status(log, total_s2=8, total_s1=4)
    assert st["stage"] in ("s2", "s1")
    assert st["epoch"] == 3
    assert 0 <= st["pct"] <= 100
    assert st["done"] is False


def test_parse_status_done_on_marker():
    log = "INFO:pomni:====> Epoch: 4\n[ft] DONE GPT_SoVITS_Pomni copied\n"
    st = vf.parse_training_status(log, total_s2=8, total_s1=4)
    assert st["done"] is True


def test_can_finetune_false_without_cuda(monkeypatch):
    monkeypatch.setattr(vf, "_gpu_vram_gb", lambda: 0.0)
    monkeypatch.setattr(vf, "_sovits_installed", lambda: True)
    assert vf.can_finetune()["ok"] is False


def test_can_finetune_true_with_gpu_and_env(monkeypatch):
    monkeypatch.setattr(vf, "_gpu_vram_gb", lambda: 6.0)
    monkeypatch.setattr(vf, "_sovits_installed", lambda: True)
    assert vf.can_finetune()["ok"] is True


def test_build_dataset_from_picks_cuts_regions(tmp_path, monkeypatch):
    # fixture: a 6s sine wav; one pick with two regions
    import wave, struct, math
    wavp = tmp_path / "edit_v1.wav"
    with wave.open(str(wavp), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(32000)
        for i in range(32000*6):
            w.writeframes(struct.pack("<h", int(8000*math.sin(i/20))))
    monkeypatch.setattr("character_creator.voice_transcribe.transcribe_file",
                        lambda p, **k: {"text": "hello there", "language": "en"})
    n = vf.build_dataset_from_picks("testc", [{"edit_wav": str(wavp),
        "regions": [{"start": 0.5, "end": 3.0}, {"start": 3.5, "end": 5.5}]}],
        char_root=str(tmp_path))
    assert n >= 1
    assert (tmp_path / "testc" / "voice" / "dataset" / "testc.list").exists()
