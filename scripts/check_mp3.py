from pydub import AudioSegment
try:
    audio = AudioSegment.from_mp3('client/assets/music/lisa_webb_memorial.mp3')
    print(f'Duration: {len(audio)/1000:.1f}s ({len(audio)/60000:.1f}min)')
    print(f'Channels: {audio.channels}, Rate: {audio.frame_rate}Hz')
except Exception as e:
    print(f'pydub failed: {e}')
    try:
        import subprocess
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', 'client/assets/music/lisa_webb_memorial.mp3'], capture_output=True, text=True)
        print(f'Duration: {float(r.stdout.strip()):.1f}s')
    except Exception as e2:
        print(f'ffprobe failed: {e2}')
