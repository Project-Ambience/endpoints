# tests/test_build_cmd.py
from fine_tune_habana import FineTuneProcessor, FineTuneConfig

def test_build_training_command_includes_core_flags(tmp_path):
    p = FineTuneProcessor()
    cfg = FineTuneConfig(world_size=1, num_train_epochs=1)
    cmd = p.build_training_command(
        cfg, "sshleifer/tiny-gpt2",
        str(tmp_path/"train.json"),
        str(tmp_path/"val.json"),
        str(tmp_path/"out"),
        target_modules=["q_proj","k_proj"]
    )
    joined = " ".join(cmd)
    assert "--model_name_or_path sshleifer/tiny-gpt2" in joined
    assert "--world_size 1" in joined
    assert "--num_train_epochs 1" in joined
    assert "--lora_target_modules" in joined
    assert ' "q_proj" ' in joined or '"q_proj"' in joined

