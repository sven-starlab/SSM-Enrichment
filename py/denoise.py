from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf
from noisereduce import reduce_noise
from scipy.signal import butter, sosfiltfilt


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """Collapse stereo input to mono so the denoiser works on a single waveform."""
    if audio.ndim > 1:
        return np.mean(audio, axis=1)
    return audio


def _choose_noise_profile(audio: np.ndarray, sample_rate: int):
    """Estimate how noisy the signal is and choose a denoise profile dynamically."""
    abs_audio = np.abs(audio)
    noise_floor = float(np.percentile(abs_audio, 10))
    signal_level = float(np.percentile(abs_audio, 90))
    peak = float(np.max(abs_audio)) if abs_audio.size else 1.0

    noise_ratio = noise_floor / max(signal_level, 1e-6)
    peak_ratio = noise_floor / max(peak, 1e-6)

    # Only skip denoising for genuinely clean speech. Mixed/noisy files like 987.wav
    # still need reduction, but clean English samples should remain untouched.
    if noise_ratio < 0.015 and peak_ratio < 0.01:
        return {"bypass": True}

    if noise_ratio > 0.03 or peak_ratio > 0.02:
        return {
            "prop_decrease": 0.9,
            "low_cut": 120,
            "high_cut": 3000,
            "n_fft": 4096,
            "time_mask_smooth_ms": 70,
            "freq_mask_smooth_hz": 350,
            "gain": 0.95,
        }
    if noise_ratio > 0.015 or peak_ratio > 0.01:
        return {
            "prop_decrease": 0.75,
            "low_cut": 100,
            "high_cut": 3500,
            "n_fft": 4096,
            "time_mask_smooth_ms": 80,
            "freq_mask_smooth_hz": 420,
            "gain": 0.9,
        }
    return {
        "prop_decrease": 0.55,
        "low_cut": 80,
        "high_cut": 4000,
        "n_fft": 2048,
        "time_mask_smooth_ms": 100,
        "freq_mask_smooth_hz": 500,
        "gain": 0.85,
    }


def denoise_audio(file_path: Path, output_dir: Path) -> Path:
    """Create a denoised WAV copy using an adaptive denoise profile.

    This is still isolated in its own module. The denoiser analyzes the waveform
    statistics first and then chooses a speech-preserving reduction profile based on
    the amount of background noise.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    audio, sample_rate = sf.read(str(file_path), always_2d=False)
    if audio.size == 0:
        return file_path

    audio = _to_mono(np.asarray(audio, dtype=np.float32))
    if audio.size == 0:
        return file_path

    profile = _choose_noise_profile(audio, sample_rate)
    if profile.get("bypass"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{file_path.stem}_denoised_{timestamp}.wav"
        sf.write(str(output_file), audio, sample_rate)
        return output_file

    nyquist = sample_rate / 2
    # With fs supplied, scipy expects cutoff frequencies in Hz, not normalized units.
    low_cut = profile["low_cut"]
    high_cut = min(profile["high_cut"], nyquist * 0.95)
    sos = butter(2, [low_cut, high_cut], btype="bandpass", output="sos", fs=sample_rate)
    filtered = sosfiltfilt(sos, audio)

    reduced = reduce_noise(
        y=filtered,
        sr=sample_rate,
        stationary=profile["prop_decrease"] < 0.3,
        prop_decrease=profile["prop_decrease"],
        n_fft=profile["n_fft"],
        time_mask_smooth_ms=profile["time_mask_smooth_ms"],
        freq_mask_smooth_hz=profile["freq_mask_smooth_hz"],
    )

    peak = np.max(np.abs(reduced)) if np.max(np.abs(reduced)) > 0 else 1.0
    reduced = reduced / peak * profile["gain"]
    reduced = np.clip(reduced, -1.0, 1.0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{file_path.stem}_denoised_{timestamp}.wav"
    sf.write(str(output_file), reduced, sample_rate)
    return output_file
