from pathlib import Path

from runtime import run_transcription


def list_wav_files(input_dir: Path):
    """Return all WAV files under the given directory."""
    return sorted(input_dir.rglob('*.wav'))


def transcribe_wav_file(file_path: Path, model_size: str = 'base', language: str = 'en', device: str = 'auto') -> str:
    """Transcribe with cpu, cuda, or auto, as selected in config.ini."""
    return run_transcription(file_path, model_size, language, device)


def save_transcript(output_dir: Path, file_name: str, transcript: str):
    """Save the transcript text to a .txt file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f'{file_name}.txt').write_text(transcript, encoding='utf-8')
