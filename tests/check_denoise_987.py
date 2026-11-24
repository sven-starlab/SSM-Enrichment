"""Manual regression check using the project's Windows audio environment."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'py'))
import numpy as np
import soundfile as sf
import denoise

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='ssm-denoise-check-') as directory:
    temporary = Path(directory)
    # A speech-band tone must survive bandpass filtering; isolate this from spectral reduction.
    sr = 16000
    t = np.arange(sr) / sr
    tone = 0.3 * np.sin(2 * np.pi * 1000 * t)
    source = temporary / 'tone.wav'
    sf.write(source, tone, sr)
    with patch.object(denoise, 'reduce_noise', side_effect=lambda **kw: kw['y']):
        filtered, _ = sf.read(denoise.denoise_audio(source, temporary / 'tone'))
    correlation = np.corrcoef(tone[2000:-2000], filtered[2000:-2000])[0, 1]
    assert correlation > 0.99, f'Speech band lost: correlation={correlation}'
    print(f'Speech-band regression passed: correlation={correlation:.5f}', flush=True)
    # Low sample rates must also yield valid cutoffs below Nyquist.
    sf.write(temporary / 'low.wav', tone, 6000)
    denoise.denoise_audio(temporary / 'low.wav', temporary / 'low')
    source = root / 'audio' / 'samples' / '987.wav'
    original, sr = sf.read(source)
    result = denoise.denoise_audio(source, temporary / '987')
    cleaned, clean_sr = sf.read(result)
    assert len(cleaned) == len(original) and sr == clean_sr
    assert np.isfinite(cleaned).all()
    assert np.sqrt(np.mean(cleaned ** 2)) > 0.001
    print(f'987 audio check passed: {len(cleaned) / sr:.1f}s, RMS={np.sqrt(np.mean(cleaned ** 2)):.5f}', flush=True)
    if '--transcribe' in sys.argv:
        from transcribe import transcribe_wav_file
        transcript = transcribe_wav_file(result)
        assert transcript.strip(), '987 transcription is still empty'
        print(f'987 transcription passed: {len(transcript)} characters', flush=True)
