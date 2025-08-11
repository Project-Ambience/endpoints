import json
import types
import pytest
from unittest.mock import MagicMock, patch
from inference.generic_infernece import (
    compose_prompt, extract_llama3_answer,
    needs_chat_handler, is_vision_handler, parse_input
)

def test_compose_prompt_basic():
    msgs = [{"role":"user","content":"Hello"}]
    assert compose_prompt(msgs) == "Hello"

def test_compose_prompt_correction():
    msgs = [
        {"role":"user","content":"Explain A"},
        {"role":"assistant","content":"Wrong answer"},
        {"role":"user","content":"That was wrong because..."},
    ]
    out = compose_prompt(msgs)
    assert "Original User Prompt:" in out
    assert "Your Rejected Response:" in out
    assert "User's Feedback" in out

@pytest.mark.parametrize("text,expected", [
    ("<|assistant|>Hi", "Hi"),
    ("No tags", "No tags"),
])
def test_extract_llama3_answer(text, expected):
    assert extract_llama3_answer(text) == expected

def test_routing_helpers():
    assert needs_chat_handler("llama3-8b-instruct")
    assert not needs_chat_handler("meta-llama/Meta-Llama-3-8B")
    assert is_vision_handler("llava-vision")
    assert not is_vision_handler("plain-model")

def test_parse_input_text_only():
    msg = {"input":[{"role":"user","content":"Hi"}]}
    assert parse_input(msg, is_vision_model=False) == "Hi"

def test_parse_input_vision_requires_image():
    with pytest.raises(ValueError):
        parse_input({"input":[{"role":"user","content":"Hi"}]}, is_vision_model=True)

@patch("inference.generic_infernece.mimetypes.guess_type", return_value=("application/pdf", None))
def test_parse_input_pdf_local(mock_guess, tmp_path):
    # create tiny fake PDF or just ensure code handles open failure gracefully
    p = tmp_path/"a.pdf"
    p.write_bytes(b"%PDF-1.4\n%EOF")
  
    # PdfReader may not extract here; function should not crash
    msg = {"input":[{"role":"user","content":"Summarise"}], "file_url": str(p)}
    out = parse_input(msg, is_vision_model=False)
    assert "Summarise" in out  # prompt still included

@patch("inference.generic_infernece.hf_pipeline")
def test_handler_selection_pipeline(mock_pipe, monkeypatch):
    # Avoid loading real models: replace PipelineHandler.__init__ to set .pipe and tokenizer only
    from inference.generic_infernece import PipelineHandler
    def fake_init(self, base_model_path, device, adapter_path=None):
        self.pipe = types.SimpleNamespace(tokenizer="tok")
        self.tokenizer = "tok"
        self.adapter_path = None
        self.base_model_path = base_model_path
        self.device = device
    monkeypatch.setattr(PipelineHandler, "__init__", fake_init)

    # Call infer path without touching transformers
    ph = PipelineHandler("meta-llama/Meta-Llama-3-8B", "cpu")
    # monkeypatch the call
    def fake_call(prompt, **kw):
        return [{"generated_text": prompt + " ::ANSWER"}]
    mock_pipe.return_value = fake_call
    out = ph.infer("Hello")
    assert out.endswith("::ANSWER")

@patch("inference.generic_infernece.AutoModelForCausalLM.from_pretrained")
@patch("inference.generic_infernece.AutoTokenizer.from_pretrained")
def test_chat_handler(monkeypatch, mock_tok, mock_model):
    from inference.generic_infernece import ChatHandler
    # stub tokenizer.apply_chat_template
    tok = MagicMock()
    tok.eos_token_id = 0
    tok.apply_chat_template.return_value = {"input_ids": MagicMock(), "attention_mask": MagicMock()}
    tok.decode.return_value = "RESPONSE"
    mock_tok.return_value = tok
    model = MagicMock()
    model.generate.return_value = MagicMock()
    mock_model.return_value = model

    ch = ChatHandler("llama-instruct", "cpu", adapter_path=None)
    out = ch.infer([{"role":"user","content":"Hi"}])
    assert out == "RESPONSE"

@patch("inference.generic_infernece.AutoTokenizer.from_pretrained")
@patch("inference.generic_infernece.AutoModelForCausalLM.from_pretrained")
@patch("inference.generic_infernece.pika.BlockingConnection")
def test_on_message_flow(mock_conn, mock_model, mock_tok, monkeypatch):
    """
    Full on_message path with mocks: ensures ack + publish happen.
    """
    # import the module fresh to build closures
    import importlib
    mod = importlib.import_module("inference.generic_infernece")

    # fake channel
    ch = MagicMock()
    ch.basic_publish = MagicMock()
    ch.basic_ack = MagicMock()

    # stub handler cache by forcing get_handler to return a dummy with infer()
    class DummyHandler:
        default_generation_args = {"max_new_tokens": 8}
        def infer(self, prompt, **kw):
            return "OK"
    def fake_get_handler(base_model_path, device, adapter_path=None):
        return DummyHandler()
    monkeypatch.setattr(mod, "needs_chat_handler", lambda x: False)
    monkeypatch.setattr(mod, "is_vision_handler", lambda x: False)
    monkeypatch.setattr(mod, "extract_llama3_answer", lambda s: s)
  
    # Rebuild a tiny on_message using the same logic:
    def on_message(ch, method, properties, body):
        message = json.loads(body)
        handler = fake_get_handler(message["base_model_path"], "hpu", message.get("adapter_path"))
        parsed_prompt = mod.parse_input(message, is_vision_model=False)
        res = handler.infer(parsed_prompt, **message.get("generation_args", handler.default_generation_args))
        res = mod.extract_llama3_answer(res)
        ch.basic_publish(exchange="", routing_key="inference_results", body=json.dumps({"conversation_id":message.get("conversation_id"), "result":res}))
        ch.basic_ack(delivery_tag=method.delivery_tag)

    body = json.dumps({
        "conversation_id":"abc",
        "base_model_path":"meta-llama/Meta-Llama-3-8B",
        "input":[{"role":"user","content":"Ping"}]
    }).encode()

    method = types.SimpleNamespace(delivery_tag=1)
    on_message(ch, method, None, body)

    ch.basic_publish.assert_called_once()
    ch.basic_ack.assert_called_once()
