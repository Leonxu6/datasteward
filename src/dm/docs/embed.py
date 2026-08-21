"""本地文本嵌入（离线 / CPU）。查询与文档切片走同一模型，保证向量空间一致。

后端（环境变量 DM_EMBED_BACKEND）：
  fastembed（默认）：onnxruntime 跑 bge-small-zh-v1.5（512 维），比 torch 轻、CPU 友好；
                    查询侧交给 fastembed 自动加检索指令前缀（query_embed）。
  hash：确定性哈希伪向量（无第三方依赖、可离线），**仅供单测/CI**，无真实语义。
模型首次用时下载并缓存；国内可设 HF_ENDPOINT=https://hf-mirror.com 走镜像。
"""
import contextlib
import math
import os
import sys
from pathlib import Path

# Windows 关键修复：HF 缓存默认用符号链接，普通用户无权限 → WinError 1314，缓存残缺
# （tokenizer_config.json 丢失）。禁用符号链接改为复制；并把缓存放到稳定持久目录（非 Temp，
# 避免被清理后每次重下）。须在 import fastembed/huggingface_hub 之前设置。
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

BACKEND = os.environ.get("DM_EMBED_BACKEND", "fastembed")
MODEL_NAME = os.environ.get("DM_EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
DIM = int(os.environ.get("DM_EMBED_DIM", "512"))
CACHE_DIR = os.environ.get("DM_EMBED_CACHE") or str(Path.home() / ".cache" / "dm_fastembed")

_MODEL = None


def _embedding_backend() -> str:
    value = os.environ.get("DM_EMBED_BACKEND", BACKEND)
    if not isinstance(value, str):
        raise ValueError("DM_EMBED_BACKEND must be fastembed or hash")
    value = value.strip().lower()
    if value not in {"fastembed", "hash"}:
        raise ValueError("DM_EMBED_BACKEND must be fastembed or hash")
    return value


def _normalize_texts(texts) -> list[str]:
    if isinstance(texts, str):
        values = [texts]
    else:
        if texts is None or isinstance(texts, (bytes, bytearray)):
            raise ValueError("texts must be a string or iterable of strings")
        try:
            values = list(texts)
        except TypeError as exc:
            raise ValueError("texts must be a string or iterable of strings") from exc
    if any(not isinstance(text, str) for text in values):
        raise ValueError("every embedding input must be a string")
    return values


@contextlib.contextmanager
def _silence_stdout():
    """把底层 fd1(stdout) 临时重定向到 stderr。

    关键：本模块常被 stdio-MCP 服务器（connector/mcp_server.py）在工具调用里触发。
    fastembed/onnxruntime/huggingface 加载模型时会向 **stdout** 打印（进度条/日志，且 onnxruntime
    是 C++ 层直接写 fd1，Python 层 redirect_stdout 拦不住），这会污染 MCP 的 JSON-RPC 通道
    → 客户端 BrokenResourceError → claude 拿不到工具结果而卡死。故在 fd 级别把 stdout 暂导到 stderr。
    """
    sys.stdout.flush()
    try:
        saved = os.dup(1)
    except OSError:  # 某些环境无 fd1，直接放行
        yield
        return
    try:
        os.dup2(2, 1)
        yield
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)


def _fastembed_model():
    global _MODEL
    if _MODEL is None:
        from fastembed import TextEmbedding
        _MODEL = TextEmbedding(model_name=MODEL_NAME, cache_dir=CACHE_DIR)
    return _MODEL


def _hash_vec(text):
    """确定性、L2 归一化的伪向量：字符 bigram 落桶。仅供测试，共享子串越多越相近。"""
    v = [0.0] * DIM
    s = text.replace(" ", "").replace("\n", "")
    for i in range(max(0, len(s) - 1)):
        bg = s[i:i + 2]
        h = 0
        for ch in bg:
            h = (h * 131 + ord(ch)) & 0xFFFFFFFF
        v[h % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(texts, is_query=False):
    """文本列表 → 向量列表（list[list[float]]，长度 DIM）。is_query 时走查询侧编码。"""
    texts = _normalize_texts(texts)
    if not texts:
        return []
    if _embedding_backend() == "hash":
        return [_hash_vec(t) for t in texts]
    # 全程 fd 级静默 stdout：模型加载 + 编码都可能打印，绝不能污染 stdio-MCP 的 JSON-RPC 通道
    with _silence_stdout():
        model = _fastembed_model()
        if is_query and hasattr(model, "query_embed"):
            gen = model.query_embed(texts)      # bge 查询侧由 fastembed 自动加指令前缀
        else:
            gen = model.embed(texts)
        return [list(map(float, v)) for v in gen]


def embed_one(text, is_query=False):
    return embed([text], is_query=is_query)[0]
