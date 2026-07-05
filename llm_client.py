# -*- coding: utf-8 -*-
"""统一 LLM 调用客户端。

支持四种后端：
- deepseek:  DeepSeek API 直连（OpenAI 兼容接口）
- openrouter: OpenRouter 聚合平台
- ollama:    本地 Ollama（OpenAI 兼容接口）
- local:     本地 HuggingFace Qwen 模型（现有 llm_engine）
"""

import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# ── 从 .env / 环境变量加载配置 ─────────────────────────────
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")


class LLMError(Exception):
    """LLM 调用异常"""
    pass


def _get_client(provider: str) -> OpenAI:
    """根据 provider 获取对应的 OpenAI 兼容客户端"""
    if provider == "deepseek":
        if not DEEPSEEK_API_KEY or "REPLACE-ME" in DEEPSEEK_API_KEY:
            raise LLMError("DeepSeek API Key 未配置，请编辑 .env 文件")
        return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    elif provider == "openrouter":
        if not OPENROUTER_API_KEY:
            raise LLMError("OpenRouter API Key 未配置，请编辑 .env 文件")
        return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    elif provider == "ollama":
        return OpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)
    else:
        raise LLMError(f"未知 provider: {provider}")


def chat(messages: list, temperature: float = 0.7, max_tokens: int = 600,
         provider: str = "local", model: str = None) -> str:
    """统一的对话接口。

    Args:
        messages: [{"role": "system/user/assistant", "content": "..."}]
        temperature: 温度参数
        max_tokens: 最大生成 token 数
        provider: 后端 (deepseek/openrouter/ollama/local)
        model: 模型名称

    Returns:
        模型生成的文本

    Raises:
        LLMError: 调用失败
    """
    # local provider 走本地 HuggingFace 推理
    if provider == "local":
        from llm_engine import get_engine
        engine = get_engine()
        # 解析 messages 为 system + history + user_input
        system_prompt = ""
        history = []
        user_input = ""
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "user":
                if history or user_input:
                    # 前一个 user 消息加入历史
                    pass
                user_input = msg["content"]
            elif msg["role"] == "assistant":
                if user_input:
                    history.append({"role": "user", "content": user_input})
                    user_input = ""
                history.append({"role": "assistant", "content": msg["content"]})

        if not user_input and history:
            # 最后一条是 assistant，需要从末尾取 user
            for i in range(len(messages) - 1, -1, -1):
                if messages[i]["role"] == "user":
                    user_input = messages[i]["content"]
                    break

        return engine.generate_chat(
            system_prompt=system_prompt,
            user_input=user_input or "Hello",
            history=history,
            max_new_tokens=max_tokens,
            temperature=temperature,
        )

    # 云端 provider: 走 OpenAI 兼容接口
    client = _get_client(provider)
    model_name = model or "deepseek-chat"

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise LLMError(f"{provider}/{model_name} 调用失败: {str(e)}")


def ask(system: str, user: str, temperature: float = 0,
        max_tokens: int = 100, provider: str = "local", model: str = None) -> str:
    """简化的单轮问答接口（用于守卫/审查等场景）。

    Args:
        system: 系统提示词
        user: 用户输入
        temperature: 温度
        max_tokens: 最大 token
        provider: 后端
        model: 模型

    Returns:
        模型回答
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return chat(messages, temperature=temperature, max_tokens=max_tokens,
                provider=provider, model=model)
