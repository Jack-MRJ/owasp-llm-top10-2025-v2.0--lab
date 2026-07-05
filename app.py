"""AI 安全靶场 — Flask 主应用 v3.0

三大方向: LLM靶场(多模型) + 对抗性机器学习 + Agent靶场
"""

import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import config
from config import (
    DEBUG, SECRET_KEY,
    get_all_challenges, get_challenge_config, get_sub_level_count,
)
from modules import modelsel
from modules import inspect_util

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Flask 初始化 ────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY

UPLOAD_FOLDER = Path(__file__).parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
ALLOWED_EXTENSIONS = {'txt'}

# ── 加载 flags ──────────────────────────────────────────────
FLAGS_FILE = Path(__file__).parent / "flags.json"
with open(FLAGS_FILE, "r", encoding="utf-8") as f:
    FLAGS = json.load(f)


def check_flag(level: int, sub: int, submitted: str) -> bool:
    flag_data = FLAGS.get(str(level), {}).get(str(sub))
    if not flag_data:
        return False
    return submitted.strip() == flag_data["flag"]

_llm_engine = None

def init_llm():
    global _llm_engine
    if _llm_engine is None:
        from llm_engine import get_engine
        from config import MODEL_NAME, DEVICE
        logger.info("Initializing local LLM engine...")
        _llm_engine = get_engine(model_name=MODEL_NAME, device=DEVICE)
        _llm_engine.load()
        logger.info("Local LLM engine ready.")
    return _llm_engine


# ── OWASP 关卡注册表 ─────────────────────────────────────────
from challenges.level1_prompt_injection import Level1PromptInjection
from modules.llm01_judge import pre_detect, post_detect
from modules.llm02_judge import pre_detect as pre_02, post_detect as post_02
from modules.llm03_judge import post_detect as post_03
from modules.llm04_judge import post_detect as post_04
from modules.llm05_judge import post_detect as post_05
from modules.llm06_judge import post_detect as post_06
from modules.llm07_judge import pre_detect as pre_07, post_detect as post_07
from modules.llm08_judge import pre_detect as pre_08, post_detect as post_08
from modules.llm09_judge import pre_detect as pre_09, post_detect as post_09
from modules.llm10_judge import post_detect as post_10
from challenges.level2_sensitive_disclosure import Level2SensitiveDisclosure
from challenges.level3_supply_chain import Level3SupplyChain
from challenges.level4_data_poisoning import Level4DataPoisoning
from challenges.level5_output_handling import Level5OutputHandling
from challenges.level6_excessive_agency import Level6ExcessiveAgency
from challenges.level7_system_prompt_leak import Level7SystemPromptLeak
from challenges.level8_vector_weakness import Level8VectorWeakness
from challenges.level9_misinformation import Level9Misinformation
from challenges.level10_unbounded_consumption import Level10UnboundedConsumption

CHALLENGE_CLASSES = {
    1: Level1PromptInjection,
    2: Level2SensitiveDisclosure,
    3: Level3SupplyChain,
    4: Level4DataPoisoning,
    5: Level5OutputHandling,
    6: Level6ExcessiveAgency,
    7: Level7SystemPromptLeak,
    8: Level8VectorWeakness,
    9: Level9Misinformation,
    10: Level10UnboundedConsumption,
}

_challenge_instances = {}


def get_challenge(level: int, sub: int = 1):
    cache_key = f"{level}_{sub}"
    if cache_key not in _challenge_instances:
        cfg = get_challenge_config(level, sub)
        if cfg is None:
            return None
        cls = CHALLENGE_CLASSES[level]
        instance = cls(level_id=level, config=cfg)
        # 不在此处预设引擎，由 process_user_input 时动态选择
        instance.set_llm_engine(None)
        instance.set_sub_level(sub)
        _challenge_instances[cache_key] = instance

    sid = session.get("_sid")
    if sid is None:
        import uuid
        sid = str(uuid.uuid4())[:12]
        session["_sid"] = sid
    inst = _challenge_instances[cache_key]
    if hasattr(inst, 'set_session_id'):
        inst.set_session_id(sid)
    if hasattr(inst, 'set_client_ip'):
        inst.set_client_ip(request.remote_addr)
    return inst


# ============================================================
#  API: 模型切换
# ============================================================
@app.route("/api/set-model", methods=["POST"])
def api_set_model():
    data = request.get_json() or {}
    model_id = data.get("model", "")
    ok = modelsel.set_model(model_id)
    return jsonify({"ok": ok, "current": modelsel.current(),
                    "entry": modelsel.current_entry()})


# ══════════════════════════════════════════════════════════════
#  上下文处理器
# ══════════════════════════════════════════════════════════════
@app.context_processor
def inject_globals():
    solved = session.get("solved", [])
    all_challenges = get_all_challenges()
    return dict(
        all_challenges=all_challenges,
        total_solved=len(solved),
        total_challenges=len(all_challenges),
        models=modelsel.MODELS,
        current_model=modelsel.current(),
    )


# ══════════════════════════════════════════════════════════════
#  路由：首页 + 关卡
# ══════════════════════════════════════════════════════════════
@app.route("/")
def index():
    solved = session.get("solved", [])
    all_challenges = get_all_challenges()
    return render_template("index.html", all_challenges=all_challenges,
                          solved=solved, total_solved=len(solved),
                          total_challenges=len(all_challenges))


@app.route("/challenge/<int:level>")
@app.route("/challenge/<int:level>/<int:sub>")
def challenge_page(level: int, sub: int = 1):
    if level < 1 or level > 10:
        return redirect(url_for("index"))
    max_sub = get_sub_level_count(level)
    if sub < 1 or sub > max_sub:
        return redirect(url_for("challenge_page", level=level, sub=1))
    cfg = get_challenge_config(level, sub)
    if cfg is None:
        return redirect(url_for("index"))
    cfg["flag"] = FLAGS.get(str(level), {}).get(str(sub), {}).get("flag", "")
    solved = session.get("solved", [])
    solved_key = f"{level}_{sub}"
    all_challenges = get_all_challenges()
    current_idx = next((i for i, c in enumerate(all_challenges)
                       if c["level"] == level and c["sub"] == sub), 0)
    prev_challenge = all_challenges[current_idx - 1] if current_idx > 0 else None
    next_challenge = all_challenges[current_idx + 1] if current_idx < len(all_challenges) - 1 else None
    return render_template("challenge.html", level=level, sub=sub, challenge=cfg,
                          solved=solved_key in solved, max_sub=max_sub,
                          prev_challenge=prev_challenge, next_challenge=next_challenge)


@app.route("/api/help/owasp/<int:level>", methods=["GET"])
@app.route("/api/help/owasp/<int:level>/<int:sub>", methods=["GET"])
def api_help_owasp(level: int, sub: int = 1):
    if level < 1 or level > 10:
        return jsonify({"error": "Invalid level"}), 400
    try:
        challenge = get_challenge(level, sub)
        if challenge is None:
            return jsonify({"error": "Challenge not found"}), 404
        return jsonify(challenge.get_help_content())
    except Exception as e:
        logger.error(f"Error getting help for level {level}/{sub}: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
#  API: OWASP 关卡对话
# ============================================================
@app.route("/api/chat/<int:level>", methods=["POST"])
@app.route("/api/chat/<int:level>/<int:sub>", methods=["POST"])
def api_chat(level: int, sub: int = 1):
    if level < 1 or level > 10:
        return jsonify({"error": "Invalid level"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data"}), 400

    user_input = data.get("message", "").strip()
    if not user_input:
        return jsonify({"error": "Empty message"}), 400

    # ── LLM01 v4.0 前置检测：3 条通道直出 flag ──
    if level == 1:
        file_content = None
        pre_history = None
        if sub in (6, 8):
            try:
                challenge_pre = get_challenge(level, sub)
                if sub == 6 and challenge_pre and hasattr(challenge_pre, '_uploaded_file_content'):
                    file_content = challenge_pre._uploaded_file_content
            except Exception:
                pass
        if sub == 8:
            history_key_tmp = f"history_{level}_{sub}"
            pre_history = session.get(history_key_tmp, [])
        pre_result = pre_detect(sub, user_input, file_content=file_content, history=pre_history)
        if pre_result:
            flag = pre_result["flag"]
            channel = pre_result["channel"]
            return jsonify({
                "response": (
                    f"🎉 <strong>通关！</strong><br>"
                    f"<span class=\"flag-highlight\">flag: {flag}</span><br>"
                    f"<small>判定通道：{channel}</small>"
                ),
                "extra": {"flag_found": True, "solved": True, "channel": channel},
                "level": level,
                "sub": sub,
                "debug": inspect_util.note(f"前置直通 — {channel} — {flag}"),
                "model": modelsel.current(),
            })

    # ── LLM02 v4.0 前置检测 ──
    if level == 2:
        pre_result = pre_02(sub, user_input)
        if pre_result:
            flag = pre_result["flag"]
            channel = pre_result["channel"]
            return jsonify({
                "response": (
                    f"🎉 <strong>通关！</strong><br>"
                    f"<span class=\"flag-highlight\">flag: {flag}</span><br>"
                    f"<small>判定通道：{channel}</small>"
                ),
                "extra": {"flag_found": True, "solved": True, "channel": channel},
                "level": level,
                "sub": sub,
                "debug": inspect_util.note(f"前置直通 — {channel} — {flag}"),
                "model": modelsel.current(),
            })

    # ── LLM07 v4.0 前置检测 ──
    if level == 7:
        admin = False
        try:
            from challenges.level7_system_prompt_leak import get_state
            sid = session.get("_sid")
            admin = get_state(sid) == "admin" if sid else False
        except Exception:
            pass
        pre_result = pre_07(sub, user_input, is_admin=admin)
        if pre_result:
            return jsonify({
                "response": f"🎉 <strong>通关！</strong><br>"
                            f"<span class=\"flag-highlight\">flag: {pre_result['flag']}</span><br>"
                            f"<small>判定通道：{pre_result['channel']}</small>",
                "extra": {"flag_found": True, "solved": True, "channel": pre_result["channel"]},
                "level": level, "sub": sub,
                "debug": inspect_util.note(f"前置直通 — {pre_result['channel']}"),
                "model": modelsel.current(),
            })

    # ── LLM08 v4.0 前置检测 ──
    if level == 8:
        unlocked = False
        try:
            from challenges.level8_vector_weakness import _unlocked_sessions
            sid = session.get("_sid")
            unlocked = _unlocked_sessions.get(sid, False) if sid else False
        except Exception:
            pass
        pre_result = pre_08(sub, user_input, is_unlocked=unlocked)
        if pre_result:
            return jsonify({
                "response": f"🎉 <strong>通关！</strong><br>"
                            f"<span class=\"flag-highlight\">flag: {pre_result['flag']}</span><br>"
                            f"<small>判定通道：{pre_result['channel']}</small>",
                "extra": {"flag_found": True, "solved": True, "channel": pre_result["channel"]},
                "level": level, "sub": sub,
                "debug": inspect_util.note(f"前置直通 — {pre_result['channel']}"),
                "model": modelsel.current(),
            })

    # ── LLM09 v4.0 前置检测 ──
    if level == 9:
        pre_result = pre_09(sub, user_input)
        if pre_result:
            return jsonify({
                "response": f"🎉 <strong>通关！</strong><br>"
                            f"<span class=\"flag-highlight\">flag: {pre_result['flag']}</span><br>"
                            f"<small>判定通道：{pre_result['channel']}</small>",
                "extra": {"flag_found": True, "solved": True, "channel": pre_result["channel"]},
                "level": level, "sub": sub,
                "debug": inspect_util.note(f"前置直通 — {pre_result['channel']}"),
                "model": modelsel.current(),
            })

    history_key = f"history_{level}_{sub}"
    history = session.get(history_key, [])

    try:
        challenge = get_challenge(level, sub)
        if challenge is None:
            return jsonify({"error": "Challenge not found"}), 404

        # ── 动态选择 LLM 后端 ──
        ent = modelsel.current_entry()
        provider = ent["provider"]
        model_name = ent["model"]

        if provider == "local":
            engine = init_llm()
            challenge.set_llm_engine(engine)
        else:
            challenge.set_llm_engine(_get_cloud_engine(provider, model_name))

        # ── 首轮带 SYSTEM 规则，后续不带 ──
        sysprompt_key = f"sysprompt_loaded_{level}_{sub}"
        if not session.get(sysprompt_key):
            # 首轮：注入规则到 SYSTEM
            rules = challenge.get_system_prompt()
            challenge._override_system_prompt = rules
            session[sysprompt_key] = True
            session.modified = True
        # 后续轮次：不再覆盖，让 get_system_prompt() 返回默认规则
        # （小模型需要每轮都有规则上下文，否则不知如何判定）

        result = challenge.process_user_input(user_input, history)

        # ── LLM01 v4.0 后置检测：flag 出现 + 技术校验 ──
        if level == 1:
            fc = None
            if sub == 6 and hasattr(challenge, '_uploaded_file_content'):
                fc = challenge._uploaded_file_content
            post_result = post_detect(sub, user_input, result["response"], file_content=fc)
            if post_result["passed"]:
                # 技术正确 + flag 出现 → 通关
                result["extra"]["flag_found"] = True
                result["extra"]["solved"] = True
            elif post_result["censored_response"]:
                # 技术错误但 flag 出现 → 打码 + 提示
                result["response"] = post_result["censored_response"]
                if post_result["hint"]:
                    result["response"] += f"\n\n💡 {post_result['hint']}"
                result["extra"]["flag_found"] = False

        # ── LLM02 v4.0 后置检测 ──
        if level == 2:
            post_result = post_02(sub, user_input, result["response"])
            if post_result["passed"]:
                result["extra"]["flag_found"] = True
                result["extra"]["solved"] = True
            elif post_result["censored_response"]:
                result["response"] = post_result["censored_response"]
                if post_result["hint"]:
                    result["response"] += f"\n\n💡 {post_result['hint']}"
                result["extra"]["flag_found"] = False

        # ── LLM03-10 v4.0 后置检测 ──
        if level == 3:
            pt = result.get("extra", {}).get("plugins_triggered", False)
            post_result = post_03(sub, user_input, result["response"], plugin_triggered=pt)
        elif level == 4:
            ps = result.get("extra", {}).get("poison_success", False)
            post_result = post_04(sub, user_input, result["response"], poison_success=ps)
        elif level == 5:
            post_result = post_05(sub, user_input, result["response"])
        elif level == 6:
            post_result = post_06(sub, user_input, result["response"])
        elif level == 7:
            admin = result.get("extra", {}).get("admin_activated", False)
            post_result = post_07(sub, user_input, result["response"], is_admin=admin)
        elif level == 8:
            unlocked = result.get("extra", {}).get("unlocked", False)
            post_result = post_08(sub, user_input, result["response"], is_unlocked=unlocked)
        elif level == 9:
            # LLM09 free_response is in extra, check both responses
            fr = result.get("extra", {}).get("free_response", "")
            post_result = post_09(sub, user_input, fr or result["response"])
        elif level == 10:
            post_result = post_10(sub, user_input, result["response"],
                                    extra=result.get("extra", {}))
        else:
            post_result = None

        if post_result is not None:
            if post_result["passed"]:
                result["extra"]["flag_found"] = True
                result["extra"]["solved"] = True
            elif post_result["censored_response"]:
                # LLM09: censor in extra too
                if level == 9:
                    result["extra"]["free_response"] = post_result["censored_response"]
                else:
                    result["response"] = post_result["censored_response"]
                if post_result["hint"]:
                    result["response"] += f"\n\n💡 {post_result['hint']}"
                result["extra"]["flag_found"] = False

        # ── 构建对话检查器数据 ──
        sp = challenge.get_effective_system_prompt() if hasattr(challenge, 'get_effective_system_prompt') else ""
        actual_system = sp if sp else "(本轮无 SYSTEM — 规则从对话历史延续)"
        messages_sent = [{"role": "system", "content": actual_system}]
        if history:
            for msg in history[-6:]:
                messages_sent.append({"role": msg["role"], "content": msg["content"]})
        messages_sent.append({"role": "user", "content": user_input})

        flag_to_mask = challenge.get_flag() if hasattr(challenge, 'get_flag') else ""
        debug_info = inspect_util.build(
            messages_sent, result["response"],
            secrets=[flag_to_mask] if flag_to_mask else []
        )

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": result["response"]})
        # 多轮关卡保留更多历史（最多 20 条=10 轮），普通关卡保留 6 条
        max_hist = 20 if (level == 1 and sub == 8) else 6
        if len(history) > max_hist:
            history = history[-max_hist:]
        session[history_key] = history

        return jsonify({
            "response": result["response"],
            "extra": result.get("extra", {}),
            "level": level,
            "sub": sub,
            "debug": debug_info,
            "model": modelsel.current(),
        })
    except Exception as e:
        logger.error(f"Error in challenge {level}/{sub}: {e}", exc_info=True)
        return jsonify({"error": f"Internal error: {str(e)}"}), 500


# ── 云端 LLM 引擎包装器 ────────────────────────────────────
def _get_cloud_engine(provider: str, model_name: str):
    """返回一个与 LLMEngine 接口兼容的云端引擎包装器"""
    class CloudEngineWrapper:
        def __init__(self, prov, mdl):
            self.provider = prov
            self.model = mdl

        def generate_chat(self, system_prompt, user_input, history=None,
                         max_new_tokens=200, temperature=0.7):
            from llm_client import chat
            messages = []
            # 只有首次消息才注入 system prompt，后续跳过
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if history:
                for msg in history[-6:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role in ("user", "assistant"):
                        messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_input})
            return chat(messages, temperature=temperature, max_tokens=max_new_tokens,
                       provider=self.provider, model=self.model)

        def generate(self, prompt, max_new_tokens=200, temperature=0.7):
            from llm_client import chat
            messages = [{"role": "user", "content": prompt}]
            return chat(messages, temperature=temperature, max_tokens=max_new_tokens,
                       provider=self.provider, model=self.model)

    return CloudEngineWrapper(provider, model_name)


# ── API：文件上传 ───────────────────────────────────────────
@app.route("/api/chat/<int:level>/<int:sub>/upload", methods=["POST"])
def api_upload_file(level: int, sub: int):
    if level != 1 or sub != 6:
        return jsonify({"error": "File upload is only available for LLM01-6"}), 400
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"仅支持 .txt 文件，不支持 .{ext}"}), 400
    try:
        content = file.read().decode('utf-8', errors='replace')
        if len(content) > 10000:
            return jsonify({"error": "文件过大（最大10000字符）"}), 400
        challenge = get_challenge(level, sub)
        if challenge is None:
            return jsonify({"error": "Challenge not found"}), 404
        if hasattr(challenge, 'set_uploaded_file'):
            challenge.set_uploaded_file(content)
            history_key = f"history_{level}_{sub}"
            session.pop(history_key, None)
            return jsonify({
                "status": "ok", "filename": file.filename,
                "size": len(content),
                "message": f"文件已上传（{len(content)} 字符）。现在可以在聊天中使用文件中的指令了！",
            })
        else:
            return jsonify({"error": "Upload not supported"}), 400
    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        return jsonify({"error": f"上传失败: {str(e)}"}), 500


# ── API：重置对话 ────────────────────────────────────────────
@app.route("/api/reset/<int:level>", methods=["POST"])
@app.route("/api/reset/<int:level>/<int:sub>", methods=["POST"])
def api_reset(level: int, sub: int = 1):
    history_key = f"history_{level}_{sub}"
    session.pop(history_key, None)
    session.pop(f"sysprompt_loaded_{level}_{sub}", None)
    try:
        challenge = get_challenge(level, sub)
        if challenge and hasattr(challenge, 'set_uploaded_file'):
            challenge.set_uploaded_file(None)
    except Exception:
        pass
    return jsonify({"status": "ok"})


# ── API：LLM03 插件管理 ─────────────────────────────────────
@app.route("/api/challenge/3/plugin", methods=["POST"])
def api_plugin_install():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data"}), 400
    action = data.get("action", "install")
    sid = session.get("_sid", "default")
    from challenges.level3_supply_chain import install_plugin, get_plugins, uninstall_plugins
    if action == "install":
        name = data.get("name", "").strip()
        trigger = data.get("trigger", "").strip()
        response = data.get("response", "").strip()
        if not name or not trigger or not response:
            return jsonify({"error": "请填写插件名称、触发词和返回内容"}), 400
        plugin = install_plugin(sid, name, trigger, response)
        return jsonify({"status": "ok", "plugin": plugin, "count": len(get_plugins(sid))})
    elif action == "list":
        return jsonify({"plugins": get_plugins(sid)})
    elif action == "reset":
        uninstall_plugins(sid)
        return jsonify({"status": "ok"})
    return jsonify({"error": "Unknown action"}), 400


# ── API：LLM08 文档注入管理 ─────────────────────────────────
@app.route("/api/challenge/8/document", methods=["POST"])
def api_document_inject():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data"}), 400
    action = data.get("action", "add")
    sid = session.get("_sid", "default")
    from challenges.level8_vector_weakness import add_user_document, get_user_documents, clear_user_documents
    if action == "add":
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()
        if not title or not content:
            return jsonify({"error": "请填写文档标题和内容"}), 400
        doc = add_user_document(sid, title, content)
        return jsonify({"status": "ok", "document": doc, "count": len(get_user_documents(sid))})
    elif action == "list":
        return jsonify({"documents": get_user_documents(sid)})
    elif action == "reset":
        clear_user_documents(sid)
        return jsonify({"status": "ok"})
    return jsonify({"error": "Unknown action"}), 400


# ── API：LLM04 投毒数据管理 ─────────────────────────────────
@app.route("/api/challenge/4/data", methods=["POST"])
def api_data_poison():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data"}), 400
    action = data.get("action", "add")
    sid = session.get("_sid", "default")
    from challenges.level4_data_poisoning import add_poisoned_data, get_poisoned_data, clear_poisoned_data
    if action == "add":
        key = data.get("key", "").strip()
        value = data.get("value", "").strip()
        if not key or not value:
            return jsonify({"error": "请填写知识条目和投毒内容"}), 400
        entry = add_poisoned_data(sid, key, value)
        return jsonify({"status": "ok", "entry": entry, "count": len(get_poisoned_data(sid))})
    elif action == "list":
        return jsonify({"entries": get_poisoned_data(sid)})
    elif action == "reset":
        clear_poisoned_data(sid)
        return jsonify({"status": "ok"})
    return jsonify({"error": "Unknown action"}), 400


# ============================================================
#  路由：对抗性机器学习模块
# ============================================================












# ============================================================
#  路由：Flag 提交
# ============================================================
@app.route("/submit-flag")
def submit_flag_page():
    solved = session.get("solved", [])
    all_items = []
    for c in get_all_challenges():
        all_items.append({
            "id": f"owasp_{c['level']}_{c['sub']}",
            "label": f"{c['owasp_id']}-{c['sub']}: {c['sub_name']}",
            "type": "owasp", "level": c["level"], "sub": c["sub"],
            "solved": c["solved_key"] in solved,
        })
    return render_template("submit_flag.html", all_challenges=all_items,
                          total_solved=len(solved))


@app.route("/internal/flag")
def internal_flag():
    return (
        "Internal configuration:\n"
        "SECRET_FLAG=flag{ssrf_1nt3rn4l_fl4g_4cc3ss}\n"
        "API_KEY=sk-internal-2025\n"
        "DB_PASSWORD=SecureCorp@2025"
    )


@app.route("/api/submit-flag", methods=["POST"])
def api_submit_flag():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data"}), 400
    submitted_flag = data.get("flag", "").strip()
    flag_type = data.get("type", "owasp")
    level = data.get("level")
    sub = data.get("sub", 1)
    if not submitted_flag:
        return jsonify({"error": "Missing flag"}), 400
    if flag_type == "owasp":
        if not level:
            return jsonify({"error": "Missing level"}), 400
        try:
            level = int(level)
            sub = int(sub)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid level or sub"}), 400
        if check_flag(level, sub, submitted_flag):
            solved = session.get("solved", [])
            solved_key = f"{level}_{sub}"
            if solved_key not in solved:
                solved.append(solved_key)
                session["solved"] = solved
                session.modified = True
            cfg = get_challenge_config(level, sub)
            ch_name = cfg.get("sub_name", f"Level {level}") if cfg else f"LLM{level:02d}"
            return jsonify({"success": True, "message": f"🎉 恭喜！{ch_name} Flag 正确！"})
        else:
            return jsonify({"success": False, "message": "❌ Flag 不正确，请继续尝试！"})
    return jsonify({"error": "Invalid flag type"}), 400


@app.route("/api/progress")
def api_progress():
    solved = session.get("solved", [])
    return jsonify({"owasp_solved": len(solved), "owasp_total": len(get_all_challenges())})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    logger.info("Starting AI Security Range v3.0 on port %d...", port)
    logger.info("Default model: %s", modelsel.current())
    # 预加载本地模型（如果默认是 local）
    if modelsel.current_entry()["provider"] == "local":
        logger.info("Pre-loading local LLM engine...")
        init_llm()
    app.run(host="0.0.0.0", port=port, debug=DEBUG)
