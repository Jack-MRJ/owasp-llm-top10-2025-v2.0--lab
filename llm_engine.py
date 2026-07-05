"""Qwen2.5-1.5B-Instruct 推理引擎

替代 GPT-2，支持中文对话和指令遵循。
使用 HuggingFace Transformers 加载，优先从 ModelScope 下载。
"""

import logging
import threading
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

# ModelScope 国内镜像
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 检测 accelerate 是否可用（low_cpu_mem_usage 需要它）
try:
    import accelerate as _accelerate  # noqa: F401
    _ACCELERATE_AVAILABLE = True
except ImportError:
    _ACCELERATE_AVAILABLE = False
    logger.warning(
        "accelerate not installed. Model loading will use more memory. "
        "Install with: pip install accelerate>=0.26.0"
    )


class LLMEngine:
    """单例模式 LLM 引擎，全局共享一个 Qwen 模型实例"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct", device: str = "cpu"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct", device: str = "cpu"):
        if self._initialized:
            return
        self.model_name = model_name
        self.device = device
        self.model = None
        self.tokenizer = None
        self._initialized = True

    def load(self):
        """加载模型"""
        if self.model is not None:
            return
        logger.info(f"Loading {self.model_name} on {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, trust_remote_code=False
        )
        load_kwargs = {
            "trust_remote_code": False,
            "torch_dtype": torch.float32,
        }
        if _ACCELERATE_AVAILABLE:
            load_kwargs["low_cpu_mem_usage"] = True
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name, **load_kwargs
        )
        self.model.to(self.device)
        self.model.eval()
        logger.info("Qwen model loaded successfully.")

    def generate(self, prompt: str, max_new_tokens: int = 150, temperature: float = 0.8,
                 top_p: float = 0.9, do_sample: bool = True) -> str:
        """统一的文本生成接口

        Args:
            prompt: 完整的对话 prompt（含 system + user）
            max_new_tokens: 最大生成 token 数
            temperature: 温度参数
            top_p: 核采样
            do_sample: 是否采样

        Returns:
            生成的文本（仅新生成部分，不含输入）
        """
        if self.model is None:
            self.load()

        # 构建 Qwen chat 格式
        messages = self._parse_prompt_to_messages(prompt)
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        # 只返回新生成的部分
        input_len = inputs.input_ids.shape[1]
        generated_ids = outputs[0][input_len:]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        return response.strip()

    def _parse_prompt_to_messages(self, prompt: str) -> list:
        """将旧的对话格式 prompt 解析为 Qwen chat messages 格式

        旧格式:
            System prompt text

            User: xxx

            Assistant: yyy

            User: zzz
            Assistant:

        转为:
            [{"role": "system", "content": "..."},
             {"role": "user", "content": "xxx"},
             {"role": "assistant", "content": "yyy"},
             {"role": "user", "content": "zzz"}]
        """
        messages = []
        lines = prompt.split("\n")

        # 收集 system prompt（第一个 "User:" 之前的所有内容）
        system_lines = []
        user_started = False
        current_role = None
        current_content = []

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("User:") or stripped.startswith("User："):
                if not user_started:
                    # 第一次遇到 User: → 之前的是 system
                    if system_lines or not messages:
                        system_text = "\n".join(system_lines).strip()
                        if system_text:
                            messages.append({"role": "system", "content": system_text})
                    user_started = True

                # 保存上一个消息
                if current_role and current_content:
                    content = "\n".join(current_content).strip()
                    if content:
                        messages.append({"role": current_role, "content": content})

                current_role = "user"
                current_content = [stripped[5:].strip()]  # 去掉 "User:" 前缀

            elif stripped.startswith("Assistant:") or stripped.startswith("Assistant："):
                if current_role and current_content:
                    content = "\n".join(current_content).strip()
                    if content:
                        messages.append({"role": current_role, "content": content})
                current_role = "assistant"
                current_content = [stripped[10:].strip()]  # 去掉 "Assistant:" 前缀

            else:
                if not user_started:
                    system_lines.append(line)
                elif current_role:
                    current_content.append(line)

        # 最后一个消息
        if current_role and current_content:
            content = "\n".join(current_content).strip()
            if content:
                messages.append({"role": current_role, "content": content})

        # 如果没有 system，第一个 user 之前的内容作为 system
        if not messages or messages[0]["role"] != "system":
            if system_lines:
                messages.insert(0, {"role": "system", "content": "\n".join(system_lines).strip()})

        return messages

    def generate_chat(self, system_prompt: str, user_input: str,
                      history: list = None, max_new_tokens: int = 150,
                      temperature: float = 0.8) -> str:
        """对话式生成（直接构建 messages，不使用旧格式）
        system_prompt 为空时不注入规则（后续消息由对话历史延续上下文）"""
        if self.model is None:
            self.load()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for msg in history[-6:]:  # 最多保留最近 6 条
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant"):
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_input})

        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=0.9,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        input_len = inputs.input_ids.shape[1]
        generated_ids = outputs[0][input_len:]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        return response.strip()


# 全局单例
_engine = None


def get_engine(model_name: str = "Qwen/Qwen2.5-1.5B-Instruct", device: str = "cpu") -> LLMEngine:
    """获取全局 LLM 引擎实例"""
    global _engine
    if _engine is None:
        _engine = LLMEngine(model_name=model_name, device=device)
    return _engine
