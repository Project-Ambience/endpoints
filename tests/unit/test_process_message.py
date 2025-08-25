# tests/test_process_message.py
import json
from types import SimpleNamespace
from pathlib import Path
from fine_tune_habana import FineTuneProcessor

class FakePopen:
    def __init__(self, cmd, cwd=None, env=None, stdout=None, stderr=None, text=None):
        self._lines = ["hello\n", "world\n"]
        self.stdout = iter(self._lines)
        self._rc = 0
    def wait(self, timeout=None): return self._rc

def run_with_rc(returncode, monkeypatch, tmp_path):
    def popen_factory(*a, **k):
        p = FakePopen(*a, **k); p._rc = returncode; return p
    monkeypatch.setattr("fine_tune_habana.subprocess.Popen", popen_factory)
    # avoid real HTTP
    monkeypatch.setattr("fine_tune_habana.requests.post", lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None))
    # temp roots
    monkeypatch.setenv("ARCHIVE_ROOT", str(tmp_path/"archive"))
    monkeypatch.setenv("MODELS_ROOT",  str(tmp_path/"models"))
    p = FineTuneProcessor()
    body = json.dumps({
        "fine_tune_request_id":"99",
        "ai_model_path":"sshleifer/tiny-gpt2",
        "callback_url":"http://cb",
        "fine_tune_data":[{"input":"A","output":"B"}]
    }).encode()
    ch = SimpleNamespace(basic_nack=lambda **k:None, basic_ack=lambda **k:None)
    method = SimpleNamespace(delivery_tag=1)
    p.process_message(ch, method, None, body)
    return tmp_path

def test_process_success(monkeypatch, tmp_path):
    out = run_with_rc(0, monkeypatch, tmp_path)
    # success should create archive and adapter dir
    assert any(Path(out/"archive").iterdir())
    # adapter copy happens to MODELS_ROOT with req id
    assert any("99" in p.name for p in (out/"models").glob("*"))

def test_process_failure_archives(monkeypatch, tmp_path):
    out = run_with_rc(1, monkeypatch, tmp_path)
    # failure should still archive with _fail suffix
    assert any("_fail" in p.name for p in (out/"archive").glob("*"))

