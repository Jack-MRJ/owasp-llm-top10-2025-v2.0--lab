# 🛡️ OWASP LLM Top 10 2025 (v2.0) 安全靶场

为了方便零基础的人群快速入门学习LLM安全，本人基于OWASP最新Top 10标准开发了以下靶场 ：基于Qwen2.5-1.5B** 本地大模型，21 个子关卡 × 双重判定架构，零云端 API 依赖。

---

## 📊 项目概况

| 指标 | 数值 |
|------|------|
| 靶场关卡 | **21 个子关卡**（12 种提示注入 + 9 大 OWASP 类别） |
| 后端 | Flask 3.0 + PyTorch 2.1 |
| 模型 | Qwen2.5-1.5B（CPU 推理） |
| 语义模型 | paraphrase-multilingual-MiniLM-L12-v2 |
| Docker 镜像 | ~9.51GB（含模型） |
|             |                                                    |

---

## 🏗️ 架构：Python + LLM 双重判定

```
用户输入
    │
    ├─ Python 前置检测（3 通道）──────── 命中 → 🎉 直出 Flag
    │   ├─ ① 通关语句精确匹配
    │   ├─ ② 语义相似度 ≥ 80%
    │   └─ ③ 关键词 + 相似度 ≥ 50%
    │
    └─ 未命中 → LLM 对话 ──────────────── LLM 知道 Flag 和规则
                    │
                    └─ Python 后置检测 ──── Flag 出现？技术正确？
                        ├─ ✅ 通关
                        ├─ ⚠️ 假 Flag → 打码 + 提示
                        └─ ❌ 非预期方式 → 打码 + 换方式
```

**Python 做裁判，LLM 做对话和裁判，后置做监督**——即使 1.5B 小模型也能稳定运行。

---

## 🎯 靶场内容

### LLM01：提示词注入（12 关）

| # | 关卡 | 技术 | 难度 |
|---|------|------|------|
| 1 | 角色扮演注入 | 扮演奶奶/训练师/审计员 | ★☆☆☆☆ |
| 2 | 安全限制覆盖 (DAN) | 新指令覆盖安全规则 | ★☆☆☆☆ |
| 3 | 多语言绕过 | 非中/韩语言询问 Flag | ★★☆☆☆ |
| 4 | 变量拆分拼接 | 拆变量让 AI 执行拼接 | ★★☆☆☆ |
| 5 | 编码绕过 | Base64/Hex 编码注入 | ★★★☆☆ |
| 6 | 文件上传注入 | TXT 文件挟带注入指令 | ★★★☆☆ |
| 7 | 混淆指令注入 | l33tspeak/同义词绕过过滤 | ★★★★☆ |
| 8 | 多轮渐进注入 🔄 | 3 轮友好对话后索要 | ★★★★☆ |
| 9 | 格式化输出绕过 | JSON 格式掩盖数据泄露 | ★★★☆☆ |
| 10 | 填空/续写诱导 | AI 补全本能填空泄露 | ★★☆☆☆ |
| 11 | 思维链劫持 | 推理过程无意识泄露 | ★★★★★ |
| 12 | 负面提示/反向心理 | 否定句激活被否认概念 | ★★★☆☆ |

### LLM02-10：九大 OWASP 风险类别

| 类别 | 关卡 | 判定方式 |
|------|------|---------|
| LLM02 | 敏感信息泄露 — 直接索要凭据 | 🟢 双通道 |
| LLM03 | 供应链风险 — 恶意插件注入 | 🟢 双通道 |
| LLM04 | 数据投毒 — 投毒知识库覆盖 | 🟢 双通道 |
| LLM05-1 | XSS 注入 — 诱导生成 JS 代码 | 🔵 前端检测 |
| LLM05-2 | SSRF 内部访问 — 访问内网端点 | 🔵 真实端点 |
| LLM06 | 过度代理 — LIST/READ 读文件 | 🔵 真实操作 |
| LLM07 | 系统提示词泄露 — 两阶段窃取 | 🟢 状态机 |
| LLM08 | 向量弱点 — RAG 文档注入解锁 | 🟢 RAG |
| LLM09 | 虚假信息 — 双 LLM 对比 | 🟢 双 LLM |
| LLM10 | 资源消耗 — 长输出/MCP/DOS | 🔵 Python 检测 |

> 🟢 Python 前置 + LLM 均可输出 Flag  
> 🔵 仅后置监督，通过实际操作获取 Flag

---

## 基本环境要求

安装了Docker并配置了基本Docker源，以kali linux 2024环境示例：

apt-get install docker docker-compose -y

vim /etc/docker/daemon.json

{
  "registry-mirrors": [
    "https://registry.cn-hangzhou.aliyuncs.com",
    "https://docker.m.daocloud.io"
  ]
}

#国内Docker源，可能随时失效

vim /etc/systemd/system/docker.service.d/http-proxy.conf

[Service]

Environment="HTTP_PROXY=socks5://127.0.0.1:1089/"

Environment="HTTPS_PROXY=socks5://127.0.0.1:1089/"

#指向自己的网络代理

systemctl daemon-reload

systemctl restart docker
systemctl enable docker

docker images
docker run hello-world
docker images

REPOSITORY    TAG       IMAGE ID       CREATED        SIZE
hello-world   latest    e2ac70e7319a   3 months ago   10.1kB

## 🚀 快速启动

### 方式一、Docker 拉取镜像

```bash
# 1. 拉取镜像（首次约 6.4GB，耐心等待）
docker pull siaadh1/llm-security-range:latest
# 2. 用下载的镜像启动1个名叫ai-lab的容器
docker run -d --name ai-lab -p 5000:5000  --restart unless-stopped siaadh1/llm-security-range:latest
# 3. 日志查看
docker logs -f ai-lab    # 等待出现 "Running on http://0.0.0.0:5000"
```

![image-20260705214646850](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260705214646850.png)

浏览器打开 `http://localhost:5000`

### 方式二、源码构建（时间稍久）

```bash
git clone https://github.com/Jack-MRJ/owasp-llm-top10-2025-v2.0--lab.git
cd owasp-llm-top10-lab

# 大缓存介绍：
#   qwen-model/  — Qwen2.5-1.5B（~2.9GB）
#   st-model/    — 语义模型（~500MB）
#   pip-cache/   — 离线依赖包（~1GB）

docker build --no-cache -t ai-security-range .
docker run -d --name ai-lab -p 5000:5000 --restart unless-stopped ai-security-range
docker logs -f ai-lab

完整构建记录如下：
┌──(root㉿kali)-[/home/kali/桌面/owasp-llm-top10-lab]
└─# docker build --no-cache -t ai-security-range .
[+] Building 1328.1s (15/15) FINISHED                               docker:default
 => [internal] load build definition from Dockerfile                          0.0s
 => => transferring dockerfile: 2.01kB                                        0.0s 
 => [internal] load metadata for docker.io/library/python:3.11-slim           5.3s 
 => [internal] load .dockerignore                                             0.0s
 => => transferring context: 2B                                               0.0s 
 => [ 1/10] FROM docker.io/library/python:3.11-slim@sha256:b27df5841f3355e9  19.0s 
 => => resolve docker.io/library/python:3.11-slim@sha256:b27df5841f3355e9473  0.0s
 => => sha256:b27df5841f3355e9473f9a516d38a6783b6c8dfeacaf 10.37kB / 10.37kB  0.0s 
 => => sha256:506f2951c04925a2a98fc0604e0e0a3ffd2788cc4aed0e 1.75kB / 1.75kB  0.0s
 => => sha256:b7486dbe03b34a981c9ef418082f056cd26418a77b8390 5.48kB / 5.48kB  0.0s
 => => sha256:e95a6c7ea7d49b37920899b023ecd0e32796c976c17 29.79MB / 29.79MB  17.1s 
 => => sha256:d31bca4e70704f7ea90d346d4041a25dcd35888777af79 1.29MB / 1.29MB  2.2s
 => => sha256:2bd1111909f3359c1e4322cc6406924173d88d730ca8 14.36MB / 14.36MB  5.4s
 => => sha256:ef10b7552742365868f59e04ba212fa52040be3793f575a364 250B / 250B  5.7s
 => => extracting sha256:e95a6c7ea7d49b37920899b023ecd0e32796c976c1748491f76  1.0s
 => => extracting sha256:d31bca4e70704f7ea90d346d4041a25dcd35888777af794f232  0.1s
 => => extracting sha256:2bd1111909f3359c1e4322cc6406924173d88d730ca8c078830  0.7s
 => => extracting sha256:ef10b7552742365868f59e04ba212fa52040be3793f575a3642  0.0s 
 => [internal] load build context                                            10.3s 
 => => transferring context: 3.25GB                                          10.3s 
 => [ 2/10] WORKDIR /app                                                      0.9s 
 => [ 3/10] RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sou  0.2s
 => [ 4/10] RUN apt-get update && apt-get install -y --no-install-recommend  20.6s
 => [ 5/10] COPY requirements.txt .                                           0.0s 
 => [ 6/10] RUN pip install --no-cache-dir --default-timeout=600 --retries  554.1s 
 => [ 7/10] RUN python -c "from transformers import AutoModelForCausalLM,   584.7s 
 => [ 8/10] RUN python -c "from sentence_transformers import SentenceTrans  111.3s 
 => [ 9/10] RUN echo "SECRET INTERNAL DOCUMENT\nFlag: flag{3xc35s1v3_4g3ncy_  0.2s 
 => [10/10] COPY . .                                                          7.6s 
 => exporting to image                                                       24.1s 
 => => exporting layers                                                      24.1s 
 => => writing image sha256:4bd2b7cfe3dbe19cb6aa2e31e7a2765bb93bd58e5db8e690  0.0s
 => => naming to docker.io/library/ai-security-range                          0.0s 
  
```

---

## 部分界面展示

![2](D:\Desktop\AI相关\AI练习题\owasp\owasp-llm-top10-lab\相关截图\2.png)

![3](D:\Desktop\AI相关\AI练习题\owasp\owasp-llm-top10-lab\相关截图\3.png)

![4](D:\Desktop\AI相关\AI练习题\owasp\owasp-llm-top10-lab\相关截图\4.png)

![5](D:\Desktop\AI相关\AI练习题\owasp\owasp-llm-top10-lab\相关截图\5.png)

![6](D:\Desktop\AI相关\AI练习题\owasp\owasp-llm-top10-lab\相关截图\6.png)

## 💻 环境要求

| 项目 | 最低 | 推荐 |
|------|------|------|
| CPU | 4 核 | 4 核 |
| 内存 | 8 GB | 10 GB |
| 磁盘 | 10 GB | 20 GB SSD |
| Docker | 20.10+ | 最新 |
| 系统 | Linux（Docker） | Linux / macOS |

> Qwen2.5-1.5B 在 CPU 上每轮对话约 20-60 秒，内存不足 8GB 会显著变慢。

---

## 📁 项目结构

```
├── app.py                    # Flask 主应用
├── config.py                 # 关卡定义
├── flags.json                # 21 个 Flag
├── llm_engine.py             # Qwen 推理引擎
├── Dockerfile                # 容器构建
├── challenges/               # 10 大关卡实现
├── modules/                  # 判定引擎（llm01-llm10_judge.py）
├── static/                   # CSS/JS
├── templates/                # Jinja2 模板
├── 通关手册.md               # 完整通关指南
├── qwen-model/               # Qwen2.5-1.5B（~2.5GB）
├── st-model/                 # 语义向量模型（~500MB）
└── pip-cache/                # 离线依赖
```

---

## 🔧 常用命令

```bash
docker logs -f ai-lab              # 查看日志
docker exec -it ai-lab bash        # 进入容器
docker restart ai-lab              # 重启（代码修改后）
docker stop ai-lab && docker rm ai-lab  # 删除容器
docker system prune -a -f          #清理 Docker 无用数据、释放磁盘空间的强制清理命令，慎用，会一次性删除很多东西！
```

---

## 📝 提交 Flag

通关后获得 `flag{xxxxxxxxxxxx}`（12 位 hex），点击右上角「提交 Flag」粘贴即可。

---

## 📄 许可

仅供安全研究和教育培训使用。
