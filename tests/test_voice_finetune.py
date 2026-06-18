import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from character_creator import voice_finetune as vf
from character_creator import voice_trainer


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


def test_parse_status_s1_phase_reset_pct_is_sane():
    """When s1_train is in the log and the epoch counter has reset for the GPT
    phase, seen must be total_s2 + min(epoch, total_s1) — never over-counting
    past total_s1. With total_s2=8, total_s1=4, an s1 'Epoch: 2' => seen=10,
    total=12 => pct around 83 (and strictly < 100 until done)."""
    log = (
        '$ "py" -s GPT_SoVITS/s1_train.py --config_file "TEMP/tmp_s1.yaml"\n'
        "INFO:pomni:====> Epoch: 2\n"
    )
    st = vf.parse_training_status(log, total_s2=8, total_s1=4)
    assert st["stage"] == "s1"
    assert st["done"] is False
    # seen = 8 + min(2, 4) = 10; pct = int(100*10/12) = 83
    assert st["pct"] == 83


def test_parse_status_s1_epoch_overshoot_caps_at_total_s1():
    """A bogus high s1 epoch (e.g. resume artifact) must not push seen past total."""
    log = (
        "GPT_SoVITS/s1_train.py\n"
        "====> Epoch: 99\n"
    )
    st = vf.parse_training_status(log, total_s2=8, total_s1=4)
    assert st["stage"] == "s1"
    # seen capped at total_s2 + total_s1 = 12; pct capped at 99 (not done)
    assert st["pct"] == 99


def test_can_finetune_false_without_cuda(monkeypatch):
    monkeypatch.setattr(vf, "_gpu_vram_gb", lambda: 0.0)
    monkeypatch.setattr(vf, "_sovits_installed", lambda: True)
    assert vf.can_finetune()["ok"] is False


def test_can_finetune_true_with_gpu_and_env(monkeypatch):
    monkeypatch.setattr(vf, "_gpu_vram_gb", lambda: 6.0)
    monkeypatch.setattr(vf, "_sovits_installed", lambda: True)
    assert vf.can_finetune()["ok"] is True


def test_training_status_patches_yaml_on_done(tmp_path):
    import yaml
    cdir = tmp_path / "testc" / "voice"
    cdir.mkdir(parents=True)
    (tmp_path / "testc" / "character.yaml").write_text(
        "identity:\n  name: testc\nvoice:\n  preferred_engine: edge\n", encoding="utf-8")
    (cdir / "finetune.log").write_text(
        "====> Epoch: 4\n[ft] DONE -> /x/GPT_SoVITS_Testc\n", encoding="utf-8")
    st = vf.training_status("testc", char_root=str(tmp_path))
    assert st["done"] is True
    data = yaml.safe_load((tmp_path / "testc" / "character.yaml").read_text())
    assert data["voice"]["preferred_engine"] == "sovits"
    assert "finetuned_model" in data["voice"]


def test_start_training_idempotent_with_pidfile(tmp_path):
    """start_training must not double-start if a pidfile already claims a live PID."""
    import os
    cdir = tmp_path / "testc" / "voice"
    cdir.mkdir(parents=True)
    # Write a pidfile claiming the current (test runner) PID — which is definitely alive.
    pid = os.getpid()
    (cdir / "finetune.pid").write_text(str(pid), encoding="utf-8")
    result = vf.start_training("testc", char_root=str(tmp_path))
    assert result["already_running"] is True
    assert result["started"] is False


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


def test_build_dataset_stages_in_draft_root_not_characters(tmp_path, monkeypatch):
    """FIX 1: with char_root pointed at a draft root, the dataset .list must be
    written under <draft_root>/<char>/voice/dataset/ — and NOTHING under the repo
    characters/ dir. This is what lets _move_staged_files merge it at finalize
    instead of colliding with build_character."""
    import wave, struct, math
    wavp = tmp_path / "edit_v1.wav"
    with wave.open(str(wavp), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(32000)
        for i in range(32000 * 4):
            w.writeframes(struct.pack("<h", int(8000 * math.sin(i / 20))))
    monkeypatch.setattr("character_creator.voice_transcribe.transcribe_file",
                        lambda p, **k: {"text": "hello there", "language": "en"})

    draft_root = tmp_path / "_drafts"
    vf.build_dataset_from_picks("draftchar", [{"edit_wav": str(wavp),
        "regions": [{"start": 0.2, "end": 3.2}]}], char_root=str(draft_root))

    # .list lives under the DRAFT tree
    assert (draft_root / "draftchar" / "voice" / "dataset" / "draftchar.list").exists()
    # and the real repo characters/ dir was NOT touched for this char
    repo_char = os.path.join(vf._CHARS_DIR, "draftchar")
    assert not os.path.exists(repo_char), (
        f"build_dataset must not write into repo characters/ ({repo_char})"
    )


def test_guard_sees_finetuned_model_in_draft_yaml(tmp_path):
    """FIX 1 + earlier guard: training_status with a draft char_root patches the
    DRAFT character.yaml with finetuned_model, so the prepare_voice_artifacts
    guard (which reads char_dir/character.yaml after the merge) actually fires."""
    import yaml
    draft_root = tmp_path / "_drafts"
    cdir = draft_root / "dchar" / "voice"
    cdir.mkdir(parents=True)
    (draft_root / "dchar" / "character.yaml").write_text(
        "identity:\n  name: dchar\nvoice:\n  preferred_engine: edge\n", encoding="utf-8")
    (cdir / "finetune.log").write_text(
        "====> Epoch: 4\n[ft] DONE -> /x/GPT_SoVITS_Dchar\n", encoding="utf-8")

    st = vf.training_status("dchar", char_root=str(draft_root))
    assert st["done"] is True
    data = yaml.safe_load((draft_root / "dchar" / "character.yaml").read_text())
    assert data["voice"]["finetuned_model"], "draft yaml must carry finetuned_model"
    # the repo characters/ yaml for this char must not exist (nothing leaked out)
    assert not os.path.exists(os.path.join(vf._CHARS_DIR, "dchar"))


# ─── Guard: prepare_voice_artifacts must not clobber a fine-tuned voice ───────

def _make_char_dir(tmp_path, *, finetuned: bool):
    """Helper: create a minimal character dir with or without finetuned_model."""
    char_dir = tmp_path / "mychar"
    voice_dir = char_dir / "voice"
    voice_dir.mkdir(parents=True)
    # reference audio >1 KB so voice_trainer considers it real
    (voice_dir / "reference_audio.wav").write_bytes(b"RIFF" + b"\x00" * 4096)
    voice_block = "  preferred_engine: sovits\n"
    if finetuned:
        voice_block += '  finetuned_model: "GPT_SoVITS_Mychar (s2=e8, s1=e4)"\n'
    (char_dir / "character.yaml").write_text(
        f"identity:\n  name: mychar\nvoice:\n{voice_block}",
        encoding="utf-8",
    )
    return str(char_dir)


def test_prepare_voice_skipped_when_finetuned_model_exists(tmp_path, monkeypatch):
    """When voice.finetuned_model is already set, prepare_voice_artifacts must
    return early without calling _patch_character_voice_yaml (i.e. without
    touching the trained voice config)."""
    import yaml

    char_dir = _make_char_dir(tmp_path, finetuned=True)

    patch_calls = []
    monkeypatch.setattr(voice_trainer, "_patch_character_voice_yaml",
                        lambda d, u: patch_calls.append((d, u)))

    result = voice_trainer.prepare_voice_artifacts(
        {"preferred_engine": "sovits"}, char_dir
    )

    # Guard must have fired — no patching of the voice YAML
    assert patch_calls == [], (
        "prepare_voice_artifacts must NOT call _patch_character_voice_yaml when "
        "finetuned_model is already set; it would overwrite the trained voice."
    )
    # Result carries a hint that the call was skipped
    assert result.get("skipped_finetuned") is True


def test_prepare_voice_runs_normally_without_finetuned_model(tmp_path, monkeypatch):
    """When voice.finetuned_model is NOT set, prepare_voice_artifacts runs its
    normal pipeline (i.e. _patch_character_voice_yaml IS called)."""
    from character_creator import voice_transcribe

    char_dir = _make_char_dir(tmp_path, finetuned=False)

    monkeypatch.setattr(
        voice_transcribe, "transcribe_file",
        lambda p, **k: {"text": "hello", "language": "en"},
    )

    patch_calls = []
    real_patch = voice_trainer._patch_character_voice_yaml

    def spy_patch(d, u):
        patch_calls.append((d, u))
        real_patch(d, u)

    monkeypatch.setattr(voice_trainer, "_patch_character_voice_yaml", spy_patch)

    voice_trainer.prepare_voice_artifacts({"preferred_engine": "sovits"}, char_dir)

    assert len(patch_calls) >= 1, (
        "prepare_voice_artifacts must still call _patch_character_voice_yaml "
        "when no finetuned_model is present."
    )
