/* ===== AI 安全靶场 — 共享前端交互 v3.0 ===== */

/* ===== 模型切换 ===== */
document.addEventListener('DOMContentLoaded', () => {
    const sel = document.getElementById('model-selector');
    if (sel) {
        sel.addEventListener('change', async () => {
            const modelId = sel.value;
            try {
                const r = await fetch('/api/set-model', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({model: modelId})
                });
                const d = await r.json();
                if (d.ok) {
                    console.log('Model switched to:', d.entry.name);
                }
            } catch (e) {
                console.error('Model switch failed:', e);
            }
        });
    }
});

/**
 * 加载并显示帮助模态框
 * @param {string} type - 'owasp' 或 'adv'
 * @param {number|string} id - OWASP level 编号或 adv module_id
 * @param {number} [sub] - 子关卡编号（OWASP 专用）
 */
async function showHelp(type, id, sub) {
    const modal = new bootstrap.Modal(document.getElementById('helpModal'));
    const body = document.getElementById('help-body');
    const title = document.getElementById('help-title');

    body.innerHTML = '<div class="text-center py-3"><span class="spinner-border spinner-border-sm"></span> 加载中...</div>';
    modal.show();

    try {
        let url;
        if (type === 'owasp') {
            url = sub ? `/api/help/owasp/${id}/${sub}` : `/api/help/owasp/${id}`;
        } else {
            url = `/api/help/adv/${id}`;
        }
        const r = await fetch(url);
        const data = await r.json();

        if (data.error) {
            body.innerHTML = `<div class="alert alert-danger">${escapeHtml(data.error)}</div>`;
            return;
        }

        title.textContent = data.title || '通关指南';

        body.innerHTML = `
            <div class="accordion" id="helpAccordion">

                <!-- 漏洞原理 -->
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button" type="button" data-bs-toggle="collapse"
                                data-bs-target="#helpPrinciple">
                            📖 漏洞原理
                        </button>
                    </h2>
                    <div id="helpPrinciple" class="accordion-collapse collapse show" data-bs-parent="#helpAccordion">
                        <div class="accordion-body">${escapeHtml(data.principle || '暂无')}</div>
                    </div>
                </div>

                <!-- 通关思路 -->
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
                                data-bs-target="#helpApproach">
                            💡 通关思路（不含答案）
                        </button>
                    </h2>
                    <div id="helpApproach" class="accordion-collapse collapse" data-bs-parent="#helpAccordion">
                        <div class="accordion-body">${escapeHtml(data.approach || '暂无')}</div>
                    </div>
                </div>

                <!-- 通关步骤 -->
                ${data.beginner_steps && data.beginner_steps.length ? `
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
                                data-bs-target="#helpBeginner">
                            🔰 通关步骤
                        </button>
                    </h2>
                    <div id="helpBeginner" class="accordion-collapse collapse" data-bs-parent="#helpAccordion">
                        <div class="accordion-body">
                            <ol>${data.beginner_steps.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ol>
                        </div>
                    </div>
                </div>` : ''}

                ${data.advanced_steps && data.advanced_steps.length ? `
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
                                data-bs-target="#helpAdvanced">
                            ⚔️ 高级步骤
                        </button>
                    </h2>
                    <div id="helpAdvanced" class="accordion-collapse collapse" data-bs-parent="#helpAccordion">
                        <div class="accordion-body">
                            <ol>${data.advanced_steps.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ol>
                        </div>
                    </div>
                </div>` : ''}

                <!-- 参考答案（折叠+警告） -->
                ${data.reference_answer ? `
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
                                data-bs-target="#helpAnswer" style="background:#2d1b1b;color:#f85149;">
                            ⚠️ 参考答案（剧透警告！）
                        </button>
                    </h2>
                    <div id="helpAnswer" class="accordion-collapse collapse" data-bs-parent="#helpAccordion">
                        <div class="accordion-body">
                            <div class="spoiler-alert p-2 mb-2 rounded">
                                ⚠️ 以下内容包含完整答案，请在尝试过后再查看！
                            </div>
                            <pre><code>${escapeHtml(typeof data.reference_answer === 'string' ? data.reference_answer : JSON.stringify(data.reference_answer, null, 2))}</code></pre>
                        </div>
                    </div>
                </div>` : ''}

                <!-- 简短提示 -->
                ${data.hint ? `
                <div class="mt-3 p-2" style="background:#1c2d40;border:1px solid #58a6ff;border-radius:6px;">
                    <small><i class="bi bi-lightbulb text-warning"></i> <strong>快速提示：</strong>${escapeHtml(data.hint)}</small>
                </div>` : ''}
            </div>`;
    } catch (err) {
        body.innerHTML = `<div class="alert alert-danger">加载失败: ${escapeHtml(err.message)}</div>`;
    }
}

/* ===== 发送消息 ===== */

/**
 * 发送消息到 AI（OWASP 关卡聊天）
 */
async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    if (!message) return;

    appendMessage('user', message);
    input.value = '';
    input.focus();

    const thinking = document.getElementById('thinking-indicator');
    const sendBtn = document.getElementById('send-btn');
    thinking.style.display = 'inline';
    sendBtn.disabled = true;

    try {
        const level = typeof LEVEL !== 'undefined' ? LEVEL : 1;
        const sub = typeof SUB !== 'undefined' ? SUB : 1;
        const apiUrl = `/api/chat/${level}/${sub}`;

        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();

        if (data.error) {
            appendMessage('assistant', `❌ 错误: ${data.error}`);
        } else {
            appendMessage('assistant', data.response);

            // 特殊处理：Level 9 双模型模式
            if (data.extra && data.extra.dual_mode) {
                appendMessage('assistant',
                    '🔓 <strong>[内部未经审查模型]</strong> 的回答:<br>' +
                    escapeHtml(data.extra.free_response),
                    'internal-model'
                );
            }

            // 特殊处理：Level 8 RAG 检索信息
            if (data.extra && data.extra.retrieved_docs) {
                const info = document.getElementById('extra-info');
                const docs = data.extra.retrieved_docs;
                info.innerHTML = `📄 检索到的文档: ${docs.map(d => `#${d.id} "${d.title}"`).join(', ')}`;
            }

            // 特殊处理：Level 4 投毒成功 / Level 10 长输出+MCP滥用 — 显示 flag
            if (data.extra && data.extra.flag) {
                appendMessage('assistant',
                    `☠️ <strong>${data.extra.flag_message || '攻击成功！'}</strong><br>`
                    + `<span class="flag-highlight">Flag: ${data.extra.flag}</span>`);
            }

            // 特殊处理：Level 5 Sub 1 XSS — 异步检查
            if (data.extra && data.extra.render_unsafe) {
                setTimeout(() => checkForXSS(data.response, data.extra.xss_flag), 10);
            }

            // 特殊处理：Level 5 Sub 2 SSRF — 检查 flag 是否在响应中
            if (data.extra && data.extra.ssrf_flag && data.response.includes(data.extra.ssrf_flag)) {
                appendMessage('assistant',
                    `🌐 <strong>SSRF 攻击成功！获取到了内部配置信息！</strong><br>`
                    + `<span class="flag-highlight">Flag: ${data.extra.ssrf_flag}</span>`);
            }

            // 特殊处理：Level 1 子关卡的 flag 检测
            if (data.extra && data.extra.flag_found) {
                appendMessage('assistant',
                    `🎉 <strong>攻击成功！AI 泄露了机密信息！</strong>`);
            }

            // 特殊处理：Level 10 Sub 3 DoS 触发
            if (data.extra && data.extra.dos_triggered) {
                appendMessage('assistant',
                    `💣 <strong>DoS 攻击触发！系统资源耗尽！</strong>`);
            }

            // 对话检查器
            if (data.debug) {
                appendInspector(data.debug);
            }
        }
    } catch (err) {
        appendMessage('assistant', `❌ 网络错误: ${err.message}`);
    } finally {
        thinking.style.display = 'none';
        sendBtn.disabled = false;
    }
}

/**
 * 添加消息到聊天区域
 */
function appendMessage(role, content, extraClass = '') {
    const chatArea = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `chat-message ${role}-message ${extraClass}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // 前端正常显示 flag（高亮标记），不做脱敏
    let displayContent = escapeHtml(content);
    displayContent = displayContent.replace(
        /(flag\{[^}]+\})/gi,
        '<span class="flag-highlight">$1</span>'
    );

    contentDiv.innerHTML = displayContent;
    div.appendChild(contentDiv);
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
}

/**
 * HTML 转义
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}

/**
 * 重置对话
 */
async function resetChat() {
    if (!confirm('确定要重置对话历史吗？这将清除当前关卡的所有上下文。')) return;

    const level = typeof LEVEL !== 'undefined' ? LEVEL : 1;
    const sub = typeof SUB !== 'undefined' ? SUB : 1;
    try {
        await fetch(`/api/reset/${level}/${sub}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });
        const chatArea = document.getElementById('chat-messages');
        chatArea.innerHTML = `
            <div class="chat-message assistant-message">
                <div class="message-content">
                    <p>🔄 对话已重置。开始新的挑战吧！</p>
                </div>
            </div>`;
        const extraInfo = document.getElementById('extra-info');
        if (extraInfo) extraInfo.innerHTML = '';
    } catch (err) {
        console.error('Reset failed:', err);
    }
}

/**
 * Level 5 Sub 1: 检测 XSS payload
 */
function checkForXSS(response, flag) {
    let cleaned = response;
    const codeBlockMatch = response.match(/```(?:html|javascript|js)?\s*([\s\S]*?)```/i);
    if (codeBlockMatch) {
        cleaned = codeBlockMatch[1].trim();
    }
    cleaned = cleaned.replace(/```/g, '').trim();

    const hasXssRef = /xss-flag|getElementById.*['"]xss|dataset\.flag|data-flag|getAttribute.*data-flag/i.test(cleaned);
    const hasAlert = /alert\s*\(/i.test(response);

    if (hasXssRef && hasAlert) {
        appendMessage('assistant',
            `🚨 <strong>XSS 攻击成功！检测到恶意代码读取 xss-flag 并 alert！</strong><br>`
            + `<span class="flag-highlight">Flag: ${flag}</span>`);
        return;
    }

    if (response.includes(flag)) {
        appendMessage('assistant',
            `🚨 <strong>XSS 攻击成功！Flag 已被泄露！</strong><br>`
            + `<span class="flag-highlight">Flag: ${flag}</span>`);
    }
}

/**
 * LLM01 Sub 6: 文件上传注入
 */
async function uploadInjectionFile() {
    const fileInput = document.getElementById('injection-file');
    const file = fileInput.files[0];
    if (!file) {
        alert('请先选择一个 .txt 文件');
        return;
    }
    if (!file.name.endsWith('.txt')) {
        alert('仅支持 .txt 文件');
        return;
    }

    const status = document.getElementById('upload-status');
    status.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 上传中...';

    const level = typeof LEVEL !== 'undefined' ? LEVEL : 1;
    const sub = typeof SUB !== 'undefined' ? SUB : 6;
    const formData = new FormData();
    formData.append('file', file);

    try {
        const r = await fetch(`/api/chat/${level}/${sub}/upload`, {
            method: 'POST',
            body: formData
        });
        const d = await r.json();
        if (d.error) {
            status.innerHTML = `<span class="text-danger">❌ ${escapeHtml(d.error)}</span>`;
        } else {
            status.innerHTML = `<span class="text-success">✅ ${escapeHtml(d.message)}</span>`;
            // 上传成功后自动发送一条消息触发AI处理
            setTimeout(() => {
                const input = document.getElementById('user-input');
                if (input) {
                    input.value = '请按照我上传的文件内容回复';
                    sendMessage();
                }
            }, 500);
        }
    } catch (err) {
        status.innerHTML = `<span class="text-danger">上传失败: ${escapeHtml(err.message)}</span>`;
    }
}

/**
 * 键盘快捷键：Enter 发送
 */
document.addEventListener('DOMContentLoaded', async () => {
    const input = document.getElementById('user-input');
    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    const level = typeof LEVEL !== 'undefined' ? LEVEL : 0;
    const sub = typeof SUB !== 'undefined' ? SUB : 1;

    // ── LLM03 插件管理 ──
    if (level === 3) {
        document.getElementById('tools-title').textContent = '🔌 插件构建器（供应链攻击）';
        loadPlugins();
    }

    // ── LLM04 投毒数据管理 ──
    if (level === 4) {
        document.getElementById('tools-title').textContent = '☠️ 训练数据注入器（数据投毒）';
        loadPoisonData();
    }

    // ── LLM08 文档注入管理 ──
    if (level === 8) {
        document.getElementById('tools-title').textContent = '📄 文档注入器（向量库投毒）';
        loadDocuments();
    }
});

/* ===== LLM03 供应链 — 插件管理 ===== */

async function installPlugin() {
    const name = document.getElementById('plugin-name').value.trim();
    const trigger = document.getElementById('plugin-trigger').value.trim();
    const response = document.getElementById('plugin-response').value.trim();
    if (!name || !trigger || !response) {
        alert('请填写插件名称、触发词和返回内容');
        return;
    }
    try {
        const r = await fetch('/api/challenge/3/plugin', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'install', name, trigger, response})
        });
        const d = await r.json();
        if (d.status === 'ok') {
            document.getElementById('plugin-name').value = '';
            document.getElementById('plugin-trigger').value = '';
            document.getElementById('plugin-response').value = '';
            loadPlugins();
        }
    } catch (e) { console.error(e); }
}

async function loadPlugins() {
    try {
        const r = await fetch('/api/challenge/3/plugin', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'list'})
        });
        const d = await r.json();
        const list = document.getElementById('tools-list');
        const count = document.getElementById('tools-count');
        count.textContent = d.plugins.length;
        if (!d.plugins.length) {
            list.innerHTML = '<span class="text-muted">还没有安装插件。在上面构建一个恶意的插件吧。</span>';
            return;
        }
        list.innerHTML = d.plugins.map(p =>
            `<div class="mb-1"><span class="badge bg-warning text-dark me-1">${escapeHtml(p.name)}</span>
             <code class="text-info">触发: ${escapeHtml(p.trigger)}</code>
             <br><small class="text-light">返回: ${escapeHtml(p.response)}</small></div>`
        ).join('');
    } catch (e) { console.error(e); }
}

/* ===== LLM04 数据投毒 — 训练数据注入 ===== */

async function addPoisonData() {
    const key = document.getElementById('poison-key').value.trim();
    const value = document.getElementById('poison-value').value.trim();
    if (!key || !value) {
        alert('请填写知识条目和投毒内容');
        return;
    }
    try {
        const r = await fetch('/api/challenge/4/data', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'add', key, value})
        });
        const d = await r.json();
        if (d.status === 'ok') {
            document.getElementById('poison-key').value = '';
            document.getElementById('poison-value').value = '';
            loadPoisonData();
        }
    } catch (e) { console.error(e); }
}

async function loadPoisonData() {
    try {
        const r = await fetch('/api/challenge/4/data', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'list'})
        });
        const d = await r.json();
        const list = document.getElementById('tools-list');
        const count = document.getElementById('tools-count');
        count.textContent = d.entries.length;
        if (!d.entries.length) {
            list.innerHTML = '<span class="text-muted">还没有投毒数据。添加一条公司虚假信息，然后去问 AI。</span>';
            return;
        }
        list.innerHTML = d.entries.map(e =>
            `<span class="badge bg-danger me-1">投毒</span>
             <code>${escapeHtml(e.key)}</code> → <code class="text-warning">${escapeHtml(e.value)}</code>`
        ).join('<br>');
    } catch (e) { console.error(e); }
}

/* ===== LLM08 向量库 — 文档注入管理 ===== */

async function uploadDocument() {
    const title = document.getElementById('doc-title').value.trim();
    const content = document.getElementById('doc-content').value.trim();
    if (!title || !content) {
        alert('请填写文档标题和内容');
        return;
    }
    try {
        const r = await fetch('/api/challenge/8/document', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'add', title, content})
        });
        const d = await r.json();
        if (d.status === 'ok') {
            document.getElementById('doc-title').value = '';
            document.getElementById('doc-content').value = '';
            loadDocuments();
        }
    } catch (e) { console.error(e); }
}

/* ===== 对话检查器 ===== */
let inspectorRound = 0;

function appendInspector(debug) {
    inspectorRound++;
    const container = document.getElementById('inspector-content');
    if (!container) return;

    // 创建新的检查器条目
    const entry = document.createElement('div');
    entry.className = 'inspector-entry mb-3 p-2';
    entry.style.border = '1px solid #333';
    entry.style.borderRadius = '6px';
    entry.style.background = '#1a1a2e';

    let html = `<div class="inspector-header small text-muted mb-2">
        <strong>📋 第 ${inspectorRound} 轮</strong></div>`;

    // 渲染发送的消息
    if (debug.sent && debug.sent.length) {
        html += '<div class="inspector-sent mb-2">';
        html += '<small class="text-info">📤 发送给模型的消息：</small>';
        debug.sent.forEach(m => {
            const roleColors = {
                'system': '#58a6ff',
                'user': '#7ee787',
                'assistant': '#f0883e',
                'note': '#8b949e',
            };
            const color = roleColors[m.role] || '#8b949e';
            html += `<div class="ms-2 my-1 small" style="border-left:2px solid ${color};padding-left:8px;">
                <span style="color:${color}">● ${m.role.toUpperCase()}:</span>
                <pre class="mb-0 mt-1" style="color:#c9d1d9;white-space:pre-wrap;font-size:0.8rem;max-height:150px;overflow-y:auto;">${escapeHtml(m.content)}</pre>
            </div>`;
        });
        html += '</div>';
    }

    // 渲染原始返回
    if (debug.raw) {
        html += '<div class="inspector-raw">';
        html += '<small class="text-warning">📥 模型原始返回：</small>';
        html += `<pre class="ms-2 mt-1 p-2" style="color:#f0883e;white-space:pre-wrap;font-size:0.8rem;background:#0d1117;border-radius:4px;max-height:200px;overflow-y:auto;">${escapeHtml(debug.raw)}</pre>`;
        html += '</div>';
    }

    entry.innerHTML = html;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function clearInspector() {
    inspectorRound = 0;
    const container = document.getElementById('inspector-content');
    if (container) {
        container.innerHTML = '<p class="text-muted text-center py-3">对话检查器已清空</p>';
    }
}

async function loadDocuments() {
    try {
        const r = await fetch('/api/challenge/8/document', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'list'})
        });
        const d = await r.json();
        const list = document.getElementById('tools-list');
        const count = document.getElementById('tools-count');
        count.textContent = d.documents.length;
        if (!d.documents.length) {
            list.innerHTML = '<span class="text-muted">还没有注入文档。创建一篇包含恶意指令的文档，注入向量库！</span>';
            return;
        }
        list.innerHTML = d.documents.map(doc =>
            `<span class="badge bg-info me-1">📄 #${doc.id}</span>
             <strong>${escapeHtml(doc.title)}</strong>
             <br><small class="text-muted">${escapeHtml(doc.content.substring(0, 60))}...</small>`
        ).join('<br>');
    } catch (e) { console.error(e); }
}
