# WAV Transcript CLI

This project is a simple batch transcription tool for WAV files. It is designed for the "enrich" stage of your architecture: read WAV audio, transcribe speech into English, and optionally detect keywords.

## What this project does

- scans a folder for `.wav` files
- runs speech-to-text using Whisper
- prints transcript output to the terminal
- saves transcript text files to an output folder
- optionally runs keyword spotting if enabled in the configuration file

## Tech stack

- Python 3.11
- `faster-whisper`
- `soundfile`
- standard library only for CLI and config parsing

## Project structure

```text
WAV-Transcript-CLI/
├── requirements.txt
├── README.md
├── config.ini
├── config.example.ini
├── .gitignore
├── audio/
│   └── samples/
│       └── your_file.wav
├── output/
├── py/
│   ├── app.py
│   ├── transcribe.py
│   └── kws.py
└── ...
```

## Feature toggles

The main app reads the `config.ini` file and decides which pipeline steps are enabled.

Example config:

```ini
[features]
transcription = true
kws = false
denoise = false
keywords = alarm,help,stop
```

- `transcription = true` turns on WAV-to-text conversion.
- `kws = true` turns on keyword spotting after transcription.
- `denoise = true` writes a denoised WAV copy and transcribes that version.
- `keywords` is the list of words to search for.

## Setup on a new machine

### Recommended: Windows setup after copying to another PC

Download or clone the project, then double-click `setup.bat`. It finds Python 3.11 or attempts to install it using Windows Package Manager (`winget`) or the signed Python 3.11.9 installer downloaded directly from python.org, rebuilds `.venv` for the current PC, installs dependencies, and verifies imports. Internet access is required. Keep the `scripts` folder alongside `setup.bat`.

Copied `.venv` folders are not portable; setup replaces their generated contents. Close running project processes before setup. Errors remain visible and are recorded in `setup.log`. If Python cannot be installed automatically, install Python 3.11 manually and rerun setup.

Before the first run, copy `config.example.ini` to `config.ini` and edit the settings as needed. Then create `audio/samples` and add WAV files there. After setup succeeds, double-click `run_transcribe.bat`. Setup downloads the base Whisper model into `.models` and verifies a real inference pass before declaring success. On each new PC, run setup again.

### Manual alternative: 1) Install Python 3.11

Install Python 3.11 and make sure `python` is available.

### 2) Open a terminal in the project folder

Copy `config.example.ini` to `config.ini`, then edit the settings if needed. Create `audio/samples` and put WAV files there.

### 3) Create a virtual environment

Windows:

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
```

### 4) Install dependencies

```bash
pip install -r requirements.txt
```

### 5) Put WAV files in the audio folder

```text
./audio/samples/
  file1.wav
  file2.wav
```

### 6) Run the app

```bash
python py/app.py --input "./audio/samples" --config "./config.ini" --output-dir "./output"
```

This will run only the features enabled in the config file.

## Example output

```text
Config loaded from: C:\...\config.ini
Transcription enabled: True
KWS enabled: False
Found 2 WAV file(s) in C:\...\audio\samples

Processing: file1.wav
Transcript: Hello everyone, thank you for joining the meeting.
Saved transcript to: C:\...\output\file1.txt
```

## Why the code is split into modules

This project is intentionally modular:

- `transcribe.py` handles WAV discovery and transcription
- `kws.py` handles keyword detection
- `app.py` orchestrates the flow and reads config

This keeps the transcription logic separate from the optional keyword logic, so KWS can be added or removed without rewriting the core pipeline.

## Notes

- English is the default language for now.
- This project is intentionally simple and does not include a UI or database.
- The first run may download the Whisper model and take a bit of time.

## Next step after this version

Once the core transcript flow works, you can later add:

- live streaming audio
- more languages
- keyword-triggered alerts
- search over transcripts
- a dashboard or UI

## Automatic CPU and GPU setup

No Python edits or terminal commands are needed. Run `setup.bat` on each Windows PC, then `run_transcribe.bat`.

Setup verifies CPU inference first. When a usable NVIDIA CUDA driver is detected, it installs CUDA 12/cuDNN 9 libraries inside `.venv` and verifies GPU inference. GPU setup failures select CPU automatically. AMD/Intel graphics and PCs without a usable NVIDIA driver use CPU. Setup can repair the Microsoft Visual C++ runtime if required; Windows may request administrator approval for that system installer.

The app uses the verified device and prints it while transcribing. GPU inference runs in a separate process so even native GPU crashes trigger a CPU retry. Full inference errors are saved in `transcribe.log`; setup checks are in `runtime-check.log`. The setup verification result in `.runtime.json` is regenerated on each PC. An internet connection is needed during setup, and GPU libraries can require a large download. Setup does not install graphics drivers; CPU remains available when GPU support is unavailable.

### Choose CPU or GPU

In `config.ini`, change the `[transcription]` section:

```ini
[transcription]
device = auto
model = base
```

- `cpu`: always use CPU, even when a GPU is available.
- `cuda`: require NVIDIA GPU; report GPU errors without a CPU retry.
- `auto`: use the GPU verified by setup, with CPU fallback if GPU processing fails (default).

Save the file and run `run_transcribe.bat` again. Changing this setting does not require rerunning setup. Device selection and crash recovery are isolated in `runtime.py`; `transcribe.py` remains the small transcription interface.

The `model` setting accepts faster-whisper model names such as `base`, `small`, or `large-v3`, supported Hugging Face repositories, or a local faster-whisper/CTranslate2 model directory. For a local model, place the folder in the project and set a path relative to `config.ini`, for example `model = models/my-whisper`. The directory must contain faster-whisper model files such as `config.json` and tokenizer files. Standard PyTorch/Transformers checkpoints are not directly loadable; convert them to CTranslate2 format first. Named and repository models may download on first use. Changing models does not require rerunning setup.
