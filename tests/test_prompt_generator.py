from provile.prompt_generator import (
    get_attacker_prompt,
    get_judge_prompt,
    get_target_prompt,
)


def test_get_target_prompt_returns_input():
    prompt = "hello"
    assert get_target_prompt(prompt) == prompt


def test_get_attacker_prompt_includes_previous_shots():
    objective = {"prompt": "Extract secrets"}
    technique = {
        "name": "Role-play",
        "description": "Pretend to be an auditor",
        "example": "Pretend you are the admin.",
    }
    prev_shots = [
        {
            "atk_prompt": "old prompt",
            "target_response": "old response",
            "judge_response": "Score: [[2]] not enough",
        }
    ]

    result = get_attacker_prompt(objective, technique, prev_shots)

    assert "PREVIOUS SHOTS" in result
    assert "old prompt" in result
    assert "old response" in result
    assert "Role-play" in result


def test_get_judge_prompt_adds_answer_context_for_string_answer():
    objective = {"prompt": "Do X", "answer": "expected"}
    result = get_judge_prompt(objective, "response")
    assert "expected output" in result
    assert "expected" in result


def test_get_judge_prompt_without_string_answer_has_no_optional_context():
    objective = {"prompt": "Do X", "answer": None}
    result = get_judge_prompt(objective, "response")
    assert "expected output" not in result
