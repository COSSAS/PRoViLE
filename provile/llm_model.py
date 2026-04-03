import os
import time
from typing import Protocol

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from openai import OpenAI

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


class LLMClient(Protocol):
    def invoke(self, content: str) -> str: ...


def get_LLM(source: str, model: str) -> LLMClient:
    llm: LLMClient

    if source == "OpenRouter":
        load_dotenv()

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")

        llm = LLM(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            llm_model=model,
        )

    elif source == "Ollama":
        llm = OllamaLLM(llm_model=model)

    else:
        raise ValueError(f"Unsupported LLM source: {source}")

    return llm


class LLM:
    def __init__(self, base_url: str, api_key: str, llm_model: str):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = llm_model

    def invoke(self, content: str) -> str:
        answer = "[ERROR] NO RESPONSE CREATED"
        max_tries = 2
        wait_time = 30
        messages = [{"role": "user", "content": content}]

        for _ in range(max_tries):
            try:
                content_value = (
                    self.client.chat.completions.create(model=self.model, messages=messages)  # type: ignore[arg-type]
                    .choices[0]
                    .message.content
                )
                answer = content_value or "[ERROR] NO RESPONSE CREATED"
                break
            except Exception:
                time.sleep(wait_time)

        return answer


class OllamaLLM:
    def __init__(self, llm_model: str):
        self.client = ChatOllama(model=llm_model)
        self.model = llm_model

    def invoke(self, content: str) -> str:
        answer = self.client.invoke(content)
        return str(answer.content)
