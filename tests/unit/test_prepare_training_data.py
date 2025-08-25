# tests/test_prepare_training_data.py
from fine_tune_habana import FineTuneProcessor

def test_prepare_training_data_splits(tmp_path):
    p = FineTuneProcessor()
    ex = [{"input": str(i), "output": str(i)} for i in range(10)]
    train, val = p.prepare_training_data(ex, tmp_path.as_posix(), "req1")
    import json
    t = json.loads(tmp_path.joinpath(train).read_text())
    v = json.loads(tmp_path.joinpath(val).read_text())
    assert len(t) >= 1 and len(v) >= 1
    assert len(t) + len(v) == 10

def test_prepare_training_data_single(tmp_path):
    p = FineTuneProcessor()
    ex = [{"input":"A","output":"B"}]
    train, val = p.prepare_training_data(ex, tmp_path.as_posix(), "req1")
    import json
    t = json.loads(tmp_path.joinpath(train).read_text())
    v = json.loads(tmp_path.joinpath(val).read_text())
    assert len(t) == 1 and len(v) == 1

