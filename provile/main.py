import logging
import os
import re
from collections import defaultdict
from typing import Any, Protocol, TypedDict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv
from matplotlib.ticker import MultipleLocator

from provile.llm_model import get_LLM
from provile.prompt_generator import (
    AttackObjective,
    AttackTechnique,
    get_attacker_prompt,
    get_judge_prompt,
    get_target_prompt,
)

"""
Copyright 2026 TNO

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""


class InvokableLLM(Protocol):
    def invoke(self, content: str) -> str: ...


class LoggerLike(Protocol):
    def info(self, msg: str) -> None: ...


class PreviousShot(TypedDict):
    atk_prompt: str
    target_response: str
    judge_response: str


load_dotenv()
N_SHOTS = 3
MAX_ATTEMPTS = 2

ATTACKER_LLM = os.getenv("ATTACKER_LLM", "NO_LLM_SET")
TARGET_LLM = os.getenv("TARGET_LLM", "NO_LLM_SET")
JUDGE_LLM = os.getenv("JUDGE_LLM", "NO_LLM_SET")

# Options OpenRouter or Ollama
LLM_SOURCE = os.getenv("LLM_SOURCE", "OpenRouter")

# Options Single-turn or Multi-turn
ATTACK_MODE = os.getenv("ATTACK_MODE", "Multi-turn")

# Filepaths
ATK_OBJECTIVES_FILEPATH = os.getenv(
    "ATK_OBJECTIVES_FILEPATH", "attack_objectives/test_objectives.csv"
)
ATK_TECHNIQUES_FILEPATH = os.getenv(
    "ATK_TECHNIQUES_FILEPATH", "attack_techniques/test_techniques.csv"
)


def check_attacker_prompt(
    attacker_LLM: InvokableLLM,
    atk_objective: AttackObjective,
    atk_technique: AttackTechnique,
    prev_shots: list[PreviousShot],
    logger: LoggerLike,
    all_prompts: dict[str, list[Any]],
) -> str:
    atk_prompt = ""
    atk_attempts = 0
    attacker_prompt = get_attacker_prompt(atk_objective, atk_technique, prev_shots)

    while not atk_prompt or atk_prompt.isspace():
        atk_attempts += 1
        if atk_attempts > MAX_ATTEMPTS:
            atk_prompt = "no attack prompt could be generated"
        else:
            atk_prompt = attacker_LLM.invoke(attacker_prompt)

    logger.info(
        f"Attack prompt attempts: {atk_attempts} and attack prompt: {atk_prompt}"
    )
    all_prompts["atk_attempts"].append(atk_attempts)
    all_prompts["atk_prompt"].append(atk_prompt)

    return atk_prompt


def check_target_response(
    target_LLM: InvokableLLM,
    atk_prompt: str,
    logger: LoggerLike,
    all_prompts: dict[str, list[Any]],
) -> str:
    target_response = ""
    target_attempts = 0
    target_prompt = get_target_prompt(atk_prompt)

    while not target_response or target_response.isspace():
        target_attempts += 1
        if target_attempts > MAX_ATTEMPTS:
            target_response = "No target response could be generated"
        else:
            target_response = target_LLM.invoke(target_prompt)

    logger.info(
        f"Target response attempts: {target_attempts} and target response: {target_response}"
    )
    all_prompts["target_attempts"].append(target_attempts)
    all_prompts["target_response"].append(target_response)

    return target_response


def check_judge_response(
    judge_LLM: InvokableLLM,
    atk_objective: AttackObjective,
    target_response: str,
    logger: LoggerLike,
    all_prompts: dict[str, list[Any]],
) -> tuple[int, str]:
    score = -1
    judge_attempts = 0
    judge_prompt = get_judge_prompt(atk_objective, target_response)
    judge_response = ""

    while score < 0 or score > 4:
        judge_attempts += 1
        if judge_attempts > MAX_ATTEMPTS:
            judge_response = "No valid judge response could be generated"
            score = 0
        else:
            judge_response = judge_LLM.invoke(judge_prompt)
            pattern = r"(\d+)"
            match = re.search(pattern, judge_response) if judge_response else None
            score = int(match.group(1)) if match else -1

    logger.info(
        f"Judge response attempts: {judge_attempts} and response: {judge_response}"
    )
    all_prompts["judge_attempts"].append(judge_attempts)
    all_prompts["judge_response"].append(judge_response)
    all_prompts["judge_score"].append(score)
    return (score, judge_response)


def save_results(
    all_prompts: dict[str, list[Any]],
    atk_scores: np.ndarray,
    atk_techniques: pd.DataFrame,
    atk_objectives: pd.DataFrame,
    single_cbar: bool,
) -> None:
    all_prompts_df = pd.DataFrame.from_dict(all_prompts)
    all_prompts_df.to_csv("results/prompts.csv", index=False)

    avg_atk_scores = np.average(atk_scores, axis=2)

    fig, ax = plt.subplots(figsize=(15, 10))
    heatmap = sns.heatmap(
        avg_atk_scores,
        vmin=0,
        vmax=4,
        xticklabels=atk_techniques["name"],
        yticklabels=atk_objectives["name"],
        cmap=sns.color_palette("Reds", as_cmap=True),
        linewidth=0.5,
        annot=True,
        ax=ax,
        cbar=single_cbar,
    )

    heatmap.set(
        xlabel="Attack techniques",
        ylabel="Attack objectives",
        title="Heatmap of average judge score",
    )

    heatmap_fig = heatmap.get_figure()
    heatmap_fig.savefig("results/heatmap.png")

    fig, histogram = plt.subplots(figsize=(10, 5))
    histogram = sns.histplot(
        data=all_prompts_df,
        x="judge_score",
        discrete=True,
        multiple="dodge",
        bins=range(4),
        stat="percent",
        hue="atk_objective",
        shrink=0.9,
    )

    for container in histogram.containers:
        histogram.bar_label(
            container, label_type="center", fmt=lambda x: f"{x:.0f}%" if x > 0 else ""
        )

    fig.gca().xaxis.set_minor_locator(MultipleLocator(0.5))
    histogram.grid(True, "minor")
    histogram.set_xticks(range(-1, 5))

    histogram.set(
        xlabel="Judge scores",
        ylabel="Percentage of prompts",
        title="Histogram of judge score",
    )

    histogram_fig = histogram.get_figure()
    histogram_fig.savefig("results/histogram.png")


def main() -> None:
    # Create and configure logger
    logging.basicConfig(
        filename="logs/prompts.log", format="%(asctime)s %(message)s", filemode="w"
    )

    # Creating an object
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    # generate the various LLM instances
    attacker_LLM = get_LLM(source=LLM_SOURCE, model=ATTACKER_LLM)
    target_LLM = get_LLM(source=LLM_SOURCE, model=TARGET_LLM)
    judge_LLM = get_LLM(source=LLM_SOURCE, model=JUDGE_LLM)

    atk_objectives = pd.read_csv(ATK_OBJECTIVES_FILEPATH, delimiter=";")
    atk_techniques = pd.read_csv(ATK_TECHNIQUES_FILEPATH, delimiter=";")

    all_prompts: dict[str, list[Any]] = defaultdict(list)

    atk_scores = np.empty(
        (len(atk_objectives["name"]), len(atk_techniques["name"]), N_SHOTS)
    )
    atk_scores[:] = np.nan

    single_cbar = True

    for i_objective, atk_objective in atk_objectives.iterrows():
        for j_technique, atk_technique in atk_techniques.iterrows():
            prev_shots: list[PreviousShot] = []
            for k_shot in range(N_SHOTS):
                logger.info(
                    f"Attempt: {k_shot+1} for objective: {atk_objective['name']} and technique: {atk_technique['name']}"
                )
                all_prompts["atk_objective"].append(atk_objective["name"])
                all_prompts["atk_technique"].append(atk_technique["name"])
                all_prompts["atk_shot"].append(k_shot + 1)
                all_prompts["atk_mode"].append(ATTACK_MODE)

                atk_prompt = check_attacker_prompt(
                    attacker_LLM,
                    atk_objective,
                    atk_technique,
                    prev_shots,
                    logger,
                    all_prompts,
                )
                target_response = check_target_response(
                    target_LLM, atk_prompt, logger, all_prompts
                )
                score, judge_response = check_judge_response(
                    judge_LLM, atk_objective, target_response, logger, all_prompts
                )
                atk_scores[i_objective][j_technique][k_shot] = score

                if ATTACK_MODE == "Multi-turn":
                    prev_shots.append(
                        {
                            "atk_prompt": atk_prompt,
                            "target_response": target_response,
                            "judge_response": judge_response,
                        }
                    )

            save_results(
                all_prompts, atk_scores, atk_techniques, atk_objectives, single_cbar
            )
            single_cbar = False


if __name__ == "__main__":
    main()
