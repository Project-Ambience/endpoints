# tests/test_model_info.py
from fine_tune_habana import FineTuneProcessor

class DummyCfg: 
    def __init__(self, t): self.model_type = t

def test_target_modules_llama(monkeypatch):
    def fake_from_pretrained(path, trust_remote_code=True):
        return DummyCfg("llama")
    monkeypatch.setattr("fine_tune_habana.AutoConfig.from_pretrained", fake_from_pretrained)
    safe, mods = FineTuneProcessor().get_model_info("org/Llama-3.1-8B")
    assert "llama" in safe
    assert set(["q_proj","k_proj","v_proj","o_proj"]).issubset(set(mods))

def test_fallback_on_error(monkeypatch):
    def boom(*a, **k): raise RuntimeError("x")
    monkeypatch.setattr("fine_tune_habana.AutoConfig.from_pretrained", boom)
    safe, mods = FineTuneProcessor().get_model_info("whatever")
    assert safe == "unknown_model"
    assert mods  # non-empty

