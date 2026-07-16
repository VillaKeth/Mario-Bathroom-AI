import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import make_song_cover as m


def test_demucs_stem_path():
    p = m.demucs_stem_path("/out", "/music/My Way.mp3")
    # demucs writes <out>/htdemucs/<track-name>/vocals.wav
    assert p.replace("\\", "/") == "/out/htdemucs/My Way/vocals.wav"


def test_rvc_params_preserve_melody_by_default():
    params = m.rvc_params(0, 0.6, 0.25)
    assert params["f0up_key"] == 0        # melody preserved (NOT +12 like speech)
    assert params["index_rate"] == 0.6
    assert params["protect"] == 0.25
    assert params["f0method"] == "rmvpe"


def test_rvc_params_coerce_types():
    params = m.rvc_params("3", "0.5", "0.2")
    assert params["f0up_key"] == 3 and isinstance(params["f0up_key"], int)
    assert params["index_rate"] == 0.5 and isinstance(params["index_rate"], float)
    assert params["protect"] == 0.2 and isinstance(params["protect"], float)


def test_argparser_accepts_vocals_in():
    args = m.build_argparser().parse_args(
        ["--vocals-in", "acapella.wav", "--id", "hb", "--title", "Happy Birthday"])
    assert args.vocals_in == "acapella.wav" and args.inp is None


def test_argparser_accepts_full_mix_in():
    args = m.build_argparser().parse_args(
        ["--in", "song.mp3", "--id", "x", "--title", "X"])
    assert args.inp == "song.mp3" and args.vocals_in is None
