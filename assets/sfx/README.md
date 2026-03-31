# Sound Effects (SFX) Directory

Place WAV files here for Mario's sound effects. Expected filenames:

| Event        | Filename        | Description                     |
|------------- |---------------- |-------------------------------- |
| greeting     | `coin.wav`      | Guest arrives                   |
| game_start   | `powerup.wav`   | A game begins                   |
| roast        | `fireball.wav`  | Mario drops a roast             |
| vomit        | `pipe.wav`      | Guest is feeling sick           |
| farewell     | `star.wav`      | Guest leaves                    |
| birthday     | `1up.wav`       | Birthday person interaction     |

All files should be 16-bit WAV, 44100 Hz. Short clips (< 2 seconds) work best.

If no WAV files are present, the sound system gracefully degrades — events are logged but no audio plays.
