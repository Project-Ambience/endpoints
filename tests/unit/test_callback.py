# tests/test_callback.py
from fine_tune_habana import FineTuneProcessor
from types import SimpleNamespace

def test_send_callback_success(monkeypatch):
    captured = {}
    def fake_post(url, json, timeout):
        captured["url"]=url; captured["json"]=json; return SimpleNamespace(raise_for_status=lambda: None)
    monkeypatch.setattr("fine_tune_habana.requests.post", fake_post)
    FineTuneProcessor().send_callback("http://cb", "42", "success", "/models/adapter")
    assert captured["json"]["status"] == "success"
    assert captured["json"]["adapter_path"] == "/models/adapter"

def test_send_callback_error(monkeypatch, caplog):
    def fake_post(*a, **k): 
        class E(Exception): pass
        raise Exception("boom")
    monkeypatch.setattr("fine_tune_habana.requests.post", fake_post)
    FineTuneProcessor().send_callback("http://cb", "42", "fail", "", error="oops")
    assert any("Failed to send callback" in m for m in caplog.text.splitlines())

