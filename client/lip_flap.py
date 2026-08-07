"""Pure lip-flap pose selection from playback amplitude (no pygame).

The display polls the playback RMS level each frame while the character is
talking and picks a mouth pose; a hold time stops strobing above ~8Hz.
"""

QUIET = 0.02     # below this the mouth is closed (listening pose)
EXCITED = 0.30   # above this the mouth is wide open
HOLD_S = 0.125   # minimum time between pose changes (~8 Hz cap)

POSE_CLOSED = "speech/listening"
POSE_OPEN = "speech/talking"
POSE_WIDE = "speech/talking_excited"


def pick_pose(level: float, prev_pose: str, since_change_s: float,
              quiet: float = QUIET, excited: float = EXCITED,
              hold_s: float = HOLD_S) -> str:
    """Choose the mouth pose for the current playback level.

    Holds the previous pose until hold_s has elapsed so the sprite never
    flickers faster than the eye wants; after that it is a pure threshold.
    """
    if prev_pose and since_change_s < hold_s:
        return prev_pose
    if level is None or level < quiet:
        return POSE_CLOSED
    return POSE_WIDE if level >= excited else POSE_OPEN
