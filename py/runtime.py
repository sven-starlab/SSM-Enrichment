"""Isolated inference keeps native CUDA failures from terminating the app."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MODEL_CACHE = ROOT / '.models'
_DLL_HANDLES = []
_gpu_failed = False


def register_gpu_libraries():
    if os.name != 'nt':
        return
    import site
    directories = []
    for base in site.getsitepackages():
        nvidia = Path(base) / 'nvidia'
        if nvidia.exists():
            directories.extend(path.parent for path in nvidia.rglob('*.dll'))
    directories = sorted(set(directories))
    os.environ['PATH'] = os.pathsep.join(map(str, directories)) + os.pathsep + os.environ.get('PATH', '')
    for directory in directories:
        _DLL_HANDLES.append(os.add_dll_directory(str(directory)))


def worker(device, audio, output, probe=False, model_size='base', language='en'):
    register_gpu_libraries()
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device=device, compute_type='float16' if device == 'cuda' else 'int8', download_root=str(MODEL_CACHE))
    if probe:
        import numpy as np
        audio = np.zeros(16000, dtype=np.float32)
    segments, _ = model.transcribe(audio, language=language, vad_filter=False)
    transcript = ' '.join(segment.text for segment in segments).strip()
    if output:
        Path(output).write_text(transcript, encoding='utf-8')


def run_transcription(file_path: Path, model_size: str = 'base', language: str = 'en', device: str = 'auto') -> str:
    """Use the setup-verified GPU, retrying on CPU even after native CUDA crashes."""
    global _gpu_failed
    if device not in {'auto', 'cpu', 'cuda'}:
        raise ValueError('Transcription device must be cpu, cuda, or auto.')
    automatic = device == 'auto'
    try:
        verified_device = json.loads((ROOT / '.runtime.json').read_text(encoding='utf-8'))['device']
    except (OSError, ValueError, KeyError):
        verified_device = 'cpu'
    if automatic:
        device = 'cuda' if verified_device == 'cuda' and not _gpu_failed else 'cpu'
    with tempfile.TemporaryDirectory(prefix='ssm-transcribe-') as temporary:
        output = Path(temporary) / 'transcript.txt'
        def run(selected):
            with (ROOT / 'transcribe.log').open('a', encoding='utf-8') as log:
                return subprocess.run([
                    sys.executable, str(ROOT / 'py' / 'runtime.py'),
                    '--device', selected, '--audio', str(file_path), '--output', str(output),
                    '--model', model_size, '--language', language,
                ], stdout=log, stderr=subprocess.STDOUT).returncode
        #print('Transcribing using ' + ('NVIDIA GPU' if device == 'cuda' else 'CPU') + '...', flush=True)
        result = run(device)
        if result != 0 and device == 'cuda' and automatic:
            _gpu_failed = True
            print('GPU processing failed; retrying on CPU. Details saved in transcribe.log.', flush=True)
            result = run('cpu')
        if result != 0:
            raise RuntimeError('Transcription failed. Details saved in transcribe.log.')
        return output.read_text(encoding='utf-8')



def setup():
    log = ROOT / 'runtime-check.log'
    with log.open('w', encoding='utf-8') as stream:
        def run(args):
            return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT).returncode
        print('Downloading and testing the base speech model on CPU...', flush=True)
        if run([__file__, '--device', 'cpu', '--probe']) != 0:
            raise RuntimeError('CPU transcription check failed. See runtime-check.log.')
        device = 'cpu'
        if run(['-c', 'import ctranslate2; raise SystemExit(0 if ctranslate2.get_cuda_device_count() else 1)']) == 0:
            print('NVIDIA GPU detected. Installing local CUDA libraries (large download)...', flush=True)
            packages = ['nvidia-cublas-cu12>=12,<13', 'nvidia-cudnn-cu12>=9,<10', 'nvidia-cuda-runtime-cu12>=12,<13', 'nvidia-cuda-nvrtc-cu12>=12,<13']
            if run(['-m', 'pip', 'install', *packages]) == 0 and run([__file__, '--device', 'cuda', '--probe']) == 0:
                device = 'cuda'
            else:
                print('GPU verification failed; CPU mode is ready. Details: runtime-check.log.', flush=True)
        else:
            print('No usable NVIDIA CUDA driver detected; CPU mode is ready.', flush=True)
    (ROOT / '.runtime.json').write_text(json.dumps({'device': device}), encoding='utf-8')
    print('Verified transcription device: ' + device, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--audio')
    parser.add_argument('--output')
    parser.add_argument('--model', default='base')
    parser.add_argument('--language', default='en')
    args = parser.parse_args()
    if args.setup:
        setup()
    else:
        worker(args.device, args.audio, args.output, args.probe, args.model, args.language)
