from server.brain.behavior import Behavior, classify


def test_priority_escape_over_everything():
    b = classify({"escape": 300, "feed": 300, "bitter": 100, "groom": 300, "walk": 300})
    assert b.name == "ESCAPE" and b.emotion == "scared" and b.pose == "movement/escape"


def test_reject_needs_bitter_and_no_feeding():
    assert classify({"bitter": 50, "feed": 10}).name == "REJECT"
    assert classify({"bitter": 50, "feed": 200}).name == "FEED"  # sugar won the arbitration


def test_feed_groom_walk_nothing():
    assert classify({"feed": 249}).name == "FEED"
    assert classify({"groom": 236, "backup": 63}).name == "GROOM"
    w = classify({"walk": 5, "backup": 40})
    assert w.name == "WALK" and w.direction == "back"
    assert classify({"walk": 40, "backup": 5}).direction == "forward"
    assert classify({"ears": 50, "sugar": 0}).name == "NOTHING"
    assert classify({}).name == "NOTHING"


def test_intensity_scales_and_clamps():
    assert classify({"feed": 80}).intensity == 0.333
    assert classify({"feed": 10_000}).intensity == 1.0


def test_threshold_overrides():
    assert classify({"feed": 50}, {"feed_hz": 40}).name == "FEED"
    assert classify({"feed": 50}, {"bogus": 1}).name == "NOTHING"


def test_reject_keys_on_delivered_taste_when_stim_given():
    # When the network ignites, GNG016 drives the bitter GRN terminals centrally
    # (~46 Hz measured) although nothing bitter was tasted: that is not REJECT.
    assert classify({"bitter": 46, "groom": 263}, stim={"antenna": 100, "ears": 50}).name == "GROOM"
    assert classify({"bitter": 76, "walk": 22}, stim={}).name == "WALK"
    rej = classify({"bitter": 136, "feed": 29}, stim={"bitter": 100, "ears": 50})
    assert rej.name == "REJECT" and rej.intensity == 1.0
    assert classify({"bitter": 0, "feed": 245}, stim={"bitter": 150, "sugar": 150}).name == "FEED"


def test_emotions_exist_in_server_emotion_list():
    from server.emotions import Emotion
    valid = {v for k, v in vars(Emotion).items() if k.isupper()}
    for name in ("ESCAPE", "REJECT", "FEED", "GROOM", "WALK", "NOTHING"):
        assert Behavior(name).emotion in valid
