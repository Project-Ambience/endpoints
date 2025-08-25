# tests/test_validate_message.py
import pytest
from fine_tune_habana import FineTuneProcessor

def P(): return FineTuneProcessor()

def test_validate_ok():
    ok, err = P().validate_message({
        "fine_tune_request_id": "1",
        "ai_model_path": "sshleifer/tiny-gpt2",
        "callback_url": "http://x",
        "fine_tune_data": [{"input":"A","output":"B"}]
    })
    assert ok and err is None

@pytest.mark.parametrize("patch", [
    {"fine_tune_request_id": None},
    {"ai_model_path": None},
    {"callback_url": None},
])
def test_validate_missing(patch):
    msg = {
        "fine_tune_request_id": "1",
        "ai_model_path": "m",
        "callback_url": "http://x",
        "fine_tune_data": [{"input":"A","output":"B"}],
    }
    for k,v in patch.items(): 
        msg.pop(k, None)
    ok, err = P().validate_message(msg)
    assert not ok and "Missing required field" in err

def test_validate_ftdata_type():
    ok, err = P().validate_message({
        "fine_tune_request_id": "1",
        "ai_model_path": "m",
        "callback_url": "http://x",
        "fine_tune_data": "not-a-list"
    })
    assert not ok and "must be a list" in err

def test_validate_ftdata_empty():
    ok, err = P().validate_message({
        "fine_tune_request_id": "1",
        "ai_model_path": "m",
        "callback_url": "http://x",
        "fine_tune_data": []
    })
    assert not ok and "cannot be empty" in err

