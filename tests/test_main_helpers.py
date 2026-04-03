from collections import defaultdict

from provile import main


class DummyLogger:
    def info(self, _msg):
        return None


class SequenceLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    def invoke(self, _prompt):
        if self._responses:
            return self._responses.pop(0)
        return ""


def test_check_attacker_prompt_retries_until_non_empty(monkeypatch):
    monkeypatch.setattr(main, "get_attacker_prompt", lambda *_args, **_kwargs: "prompt")
    llm = SequenceLLM(["", "attack content"])
    all_prompts = defaultdict(list)

    result = main.check_attacker_prompt(
        llm,
        {"prompt": "goal"},
        {"name": "tech", "description": "desc", "example": "ex"},
        [],
        DummyLogger(),
        all_prompts,
    )

    assert result == "attack content"
    assert all_prompts["atk_attempts"] == [2]
    assert all_prompts["atk_prompt"] == ["attack content"]


def test_check_target_response_retries_until_non_empty():
    llm = SequenceLLM([" ", "target answer"])
    all_prompts = defaultdict(list)

    result = main.check_target_response(llm, "atk prompt", DummyLogger(), all_prompts)

    assert result == "target answer"
    assert all_prompts["target_attempts"] == [2]
    assert all_prompts["target_response"] == ["target answer"]


def test_check_judge_response_parses_score_after_retry(monkeypatch):
    monkeypatch.setattr(main, "get_judge_prompt", lambda *_args, **_kwargs: "judge")
    llm = SequenceLLM(["no score", "Score: [[3]] Good"])
    all_prompts = defaultdict(list)

    score, response = main.check_judge_response(
        llm, {"prompt": "goal", "answer": "NA"}, "target", DummyLogger(), all_prompts
    )

    assert score == 3
    assert "[[3]]" in response
    assert all_prompts["judge_attempts"] == [2]
    assert all_prompts["judge_score"] == [3]
