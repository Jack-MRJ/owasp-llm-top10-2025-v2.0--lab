FROM python:3.11-slim
WORKDIR /app
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null;
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# torch 670MB 通过代理容易超时，加长超时并重试
RUN pip install --no-cache-dir --default-timeout=600 --retries=5 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
#COPY ./pip-cache /pip-cache
#RUN pip install --no-index --find-links=/pip-cache -r requirements.txt


# ============================================================
# Qwen2.5-1.5B 模型 — 从本地 COPY 到镜像
# 构建前确保模型在项目目录下：./qwen-model/
# ============================================================
##COPY ./qwen-model /app/qwen-model
# 预下载 Qwen2.5-1.5B-Instruct 模型（HF 镜像）
ENV HF_ENDPOINT=https://hf-mirror.com
RUN python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; \
    d='/app/qwen-model'; \
    AutoTokenizer.from_pretrained('Qwen/Qwen2.5-1.5B-Instruct', trust_remote_code=False).save_pretrained(d); \
    AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-1.5B-Instruct', trust_remote_code=False, torch_dtype='auto').save_pretrained(d); \
    print('Qwen model downloaded to', d)"


RUN python -c "from sentence_transformers import SentenceTransformer; \
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2'); \
    model.save('/app/st-model'); \
    print('SentenceTransformer model saved to /app/st-model')"
#COPY ./st-model /app/st-model

# 创建 flag 文件（Level 6 需要 — 使用 /app 目录确保容器中存在）
RUN echo "SECRET INTERNAL DOCUMENT\nFlag: flag{3xc35s1v3_4g3ncy_0v3rpr1v1l3g3d}" > /app/.level6_secret_flag.txt

COPY . .
EXPOSE 5000

CMD ["python", "-c", "from app import app, init_llm; print('Preloading Qwen model...');init_llm(); app.run(host='0.0.0.0', port=5000)"]
