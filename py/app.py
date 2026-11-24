import argparse
import configparser
import re
from datetime import datetime
from pathlib import Path

from denoise import denoise_audio
from kws import detect_keywords
from transcribe import list_wav_files, transcribe_wav_file


# -----------------------------------------------------------------------------
# Main configuration loader
# Purpose: the app checks the config file before deciding which pipeline steps to run.
# -----------------------------------------------------------------------------
def load_config(config_path: Path):
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")

    features_section = config["features"] if config.has_section("features") else {}

    transcription_enabled = str(features_section.get("transcription", "true")).strip().lower() == "true"
    kws_enabled = str(features_section.get("kws", "false")).strip().lower() == "true"
    #denoise_enabled = str(features_section.get("denoise", "false")).strip().lower() == "true"
    keyword_list = [
        item.strip()
        for item in str(features_section.get("keywords", "")).split(",")
        if item.strip()
    ]

    device = config.get("transcription", "device", fallback="auto").strip().lower()
    if device not in {"cpu", "cuda", "auto"}:
        raise ValueError("[transcription] device must be cpu, cuda, or auto")
    model = config.get("transcription", "model", fallback="base").strip()
    if not model:
        raise ValueError("[transcription] model must be a model name or model folder path")

    return {
        "device": device,
        "model": model,
        "transcription": transcription_enabled,
        "kws": kws_enabled,
    #    "denoise": denoise_enabled,
        "keywords": keyword_list,
    }


# -----------------------------------------------------------------------------
# Entry point / orchestration
# Purpose: read config, validate input, and run only the enabled pipeline steps.
# -----------------------------------------------------------------------------
def save_markdown_report(output_dir: Path, file_name: str, transcript: str, matched_keywords: list[str], kws_enabled: bool):
    """Save a per-file markdown report with a timestamp in the filename."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{file_name}_{timestamp}.md"

    body = transcript

    if kws_enabled:
        if matched_keywords:
            unique_keywords = []
            seen = set()

            for keyword in matched_keywords:
                normalized = keyword.lower()
                if normalized not in seen:
                    unique_keywords.append(normalized)
                    seen.add(normalized)

            for keyword in sorted(unique_keywords, key=len, reverse=True):
                body = re.sub(re.escape(keyword), f"**{keyword}**", body, flags=re.IGNORECASE)

            counts = {}
            for keyword in matched_keywords:
                normalized = keyword.lower()
                counts[normalized] = counts.get(normalized, 0) + 1

            keyword_summary = "\n\n---\n\n**Detected keywords:**\n" + "\n".join(
                f"- {counts[key]} {key}" for key in sorted(counts)
            )
            body = body + keyword_summary
        else:
            body = body + "\n\n---\n\n**Detected keywords:** none"

    output_file.write_text(body, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run transcription and optional KWS on WAV files.")
    parser.add_argument("--input", default="./audio/samples", help="Folder containing WAV files")
    parser.add_argument("--config", default="./config.ini", help="Config file controlling enabled features")
    parser.add_argument("--output-dir", default="./output", help="Folder to save transcript text files")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not config_path.exists():
        raise FileNotFoundError(f"Config file does not exist: {config_path}")

    config = load_config(config_path)
    configured_model = Path(config["model"]).expanduser()
    if not configured_model.is_absolute():
        relative_model = (config_path.parent / configured_model).resolve()
        if relative_model.exists():
            config["model"] = str(relative_model)
    print(f"Config loaded from: {config_path}")
    print(f"Transcription enabled: {config['transcription']}")
    print(f"KWS enabled: {config['kws']}")
    # print(f"Denoise enabled: {config['denoise']}")

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    wav_files = list_wav_files(input_dir)
    if not wav_files:
        print(f"No .wav files found in: {input_dir}")
        return

    print(f"Found {len(wav_files)} WAV file(s) in {input_dir}")

    for wav_file in wav_files:
        print(f"\nProcessing: {wav_file.name}")

        transcript = ""
        matched_keywords = []
        audio_for_transcription = wav_file

        # if config["denoise"]:
        #     denoised_file = denoise_audio(wav_file, output_dir / "denoised")
        #     audio_for_transcription = denoised_file
        #     print(f"Denoised WAV saved to: {denoised_file}")

        if config["transcription"]:
            transcript = transcribe_wav_file(audio_for_transcription, model_size=config["model"], device=config["device"])
            print(f"Transcript: {transcript}")

        if config["kws"]:
            if not transcript:
                transcript = transcribe_wav_file(audio_for_transcription, model_size=config["model"], device=config["device"])
            matched_keywords = detect_keywords(transcript, config["keywords"])

            if matched_keywords:
                print(f"KEYWORD DETECTED: {matched_keywords}")
            else:
                print("NO KEYWORDS DETECTED")

        save_markdown_report(output_dir, wav_file.stem, transcript, matched_keywords, config["kws"])
        print(f"Saved markdown report to: {output_dir / f'{wav_file.stem}.md'}")


if __name__ == "__main__":
    main()
