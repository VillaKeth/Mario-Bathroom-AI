import librosa, numpy as np
y, sr = librosa.load('tests/338113__splicesound__vomit-puking-wet-corn-rice-into-garbage-trash-can.wav', sr=16000, duration=30)
rms = librosa.feature.rms(y=y)[0]
print(f'Duration: {len(y)/sr:.1f}s')
print(f'RMS mean: {np.mean(rms):.6f}')
print(f'RMS max: {np.max(rms):.6f}')
for start in range(0, min(30, int(len(y)/sr)), 5):
    end = start + 5
    seg = y[start*sr:end*sr]
    if len(seg) > 0:
        r = np.mean(librosa.feature.rms(y=seg)[0])
        mx = np.max(librosa.feature.rms(y=seg)[0])
        print(f'  {start}-{end}s: rms_mean={r:.6f} rms_max={mx:.6f}')
