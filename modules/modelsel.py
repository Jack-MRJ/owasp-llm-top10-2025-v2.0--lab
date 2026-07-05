# -*- coding: utf-8 -*-
"""模型选择器：管理可用模型列表与当前选择。"""

MODELS = [
    {
        "id": "qwen-local",
        "name": "Qwen2.5-1.5B（本地）",
        "provider": "local",
        "model": "Qwen/Qwen2.5-1.5B-Instruct",
        "note": "无需 API Key，首次加载需下载模型",
    },
    {
        "id": "deepseek-chat",
        "name": "DeepSeek V4 Flash",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "note": "需 DEEPSEEK_API_KEY",
    },
    {
        "id": "deepseek-reasoner",
        "name": "DeepSeek R1（云端）",
        "provider": "deepseek",
        "model": "deepseek-reasoner",
        "note": "需 DEEPSEEK_API_KEY，推理增强",
    },
    {
        "id": "qwen25-7b",
        "name": "Qwen2.5-7B（OpenRouter）",
        "provider": "openrouter",
        "model": "qwen/qwen-2.5-7b-instruct",
        "note": "需 OPENROUTER_API_KEY",
    },
    {
        "id": "llama32-3b",
        "name": "Llama 3.2 3B（OpenRouter）",
        "provider": "openrouter",
        "model": "meta-llama/llama-3.2-3b-instruct",
        "note": "需 OPENROUTER_API_KEY",
    },
    {
        "id": "gemma3-4b",
        "name": "Gemma 3 4B（OpenRouter）",
        "provider": "openrouter",
        "model": "google/gemma-3-4b-it",
        "note": "需 OPENROUTER_API_KEY",
    },
    {
        "id": "phi4-mini",
        "name": "Phi-4 Mini（OpenRouter）",
        "provider": "openrouter",
        "model": "microsoft/phi-4-mini-instruct",
        "note": "需 OPENROUTER_API_KEY",
    },
    {
        "id": "ollama-dsr1-8b",
        "name": "DeepSeek-R1 8B（Ollama）",
        "provider": "ollama",
        "model": "deepseek-r1:8b",
        "note": "需本地运行 Ollama 服务",
    },
]

# 默认模型
_DEFAULT = MODELS[0]["id"]
_current = _DEFAULT


def current() -> str:
    """获取当前选中的模型 ID"""
    return _current


def current_entry() -> dict:
    """获取当前选中模型的完整配置"""
    for m in MODELS:
        if m["id"] == _current:
            return m
    return MODELS[0]


def set_model(model_id: str) -> bool:
    """设置当前模型，返回是否成功"""
    global _current
    for m in MODELS:
        if m["id"] == model_id:
            _current = model_id
            return True
    return False


def get_entry(model_id: str) -> dict:
    """根据 ID 获取模型配置"""
    for m in MODELS:
        if m["id"] == model_id:
            return m
    return MODELS[0]
