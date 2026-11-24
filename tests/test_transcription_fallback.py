import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'py'))
import transcribe
import runtime


class TranscriptionFallbackTests(unittest.TestCase):
    def test_explicit_cpu_overrides_verified_gpu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.runtime.json').write_text(json.dumps({'device': 'cuda'}))
            def run(command, **kwargs):
                self.assertEqual(command[command.index('--device') + 1], 'cpu')
                Path(command[command.index('--output') + 1]).write_text('CPU result')
                return SimpleNamespace(returncode=0)
            with patch.object(runtime, 'ROOT', root), patch.object(runtime.subprocess, 'run', side_effect=run):
                self.assertEqual(transcribe.transcribe_wav_file(Path('sample.wav'), device='cpu'), 'CPU result')

    def test_explicit_cuda_reports_failure_without_cpu_retry(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'ROOT', Path(directory)), patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=1)) as run:
            with self.assertRaisesRegex(RuntimeError, 'transcribe.log'):
                transcribe.transcribe_wav_file(Path('sample.wav'), device='cuda')
            self.assertEqual(run.call_count, 1)
            self.assertIn('cuda', run.call_args.args[0])

    def test_native_gpu_crash_retries_cpu_and_stays_on_cpu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.runtime.json').write_text(json.dumps({'device': 'cuda'}))
            devices = []
            def run(command, **kwargs):
                device = command[command.index('--device') + 1]
                devices.append(device)
                if device == 'cuda':
                    return SimpleNamespace(returncode=3221225477)
                Path(command[command.index('--output') + 1]).write_text('hello')
                return SimpleNamespace(returncode=0)
            with patch.object(runtime, 'ROOT', root), patch.object(runtime, '_gpu_failed', False), patch.object(runtime.subprocess, 'run', side_effect=run):
                self.assertEqual(runtime.run_transcription(Path('sample.wav')), 'hello')
                self.assertEqual(runtime.run_transcription(Path('sample.wav')), 'hello')
            self.assertEqual(devices, ['cuda', 'cpu', 'cpu'])

    def test_cpu_failure_reports_log(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'ROOT', Path(directory)), patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
            with self.assertRaisesRegex(RuntimeError, 'transcribe.log'):
                runtime.run_transcription(Path('sample.wav'))

    def test_setup_does_not_claim_success_when_cpu_probe_fails(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'ROOT', Path(directory)), patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
            with self.assertRaisesRegex(RuntimeError, 'CPU transcription check failed'):
                runtime.setup()
            self.assertFalse((Path(directory) / '.runtime.json').exists())

    def test_failed_gpu_probe_selects_cpu(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'ROOT', Path(directory)), patch.object(runtime.subprocess, 'run', side_effect=[SimpleNamespace(returncode=x) for x in [0, 0, 0, 1]]):
            runtime.setup()
            self.assertEqual(json.loads((Path(directory) / '.runtime.json').read_text())['device'], 'cpu')

    def test_successful_gpu_probe_selects_cuda(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'ROOT', Path(directory)), patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
            runtime.setup()
            self.assertEqual(json.loads((Path(directory) / '.runtime.json').read_text())['device'], 'cuda')


if __name__ == '__main__':
    unittest.main()
