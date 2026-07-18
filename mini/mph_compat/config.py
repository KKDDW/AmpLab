"""Runtime configuration for COMSOL Multiphysics MCP."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / "env.local"
CACHE_DIR = Path(os.getenv("COMSOL_AGENT_CACHE_DIR", str(PROJECT_ROOT / "cache")))

if load_dotenv is not None:
    load_dotenv(ENV_FILE)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


DEFAULT_BACKEND = os.getenv("COMSOL_AGENT_DEFAULT_BACKEND", "mph").strip().lower() or "mph"
PDF_DIR = Path(os.getenv("COMSOL_AGENT_PDF_DIR", str(PROJECT_ROOT / "pdf")))
KNOWLEDGE_DB_DIR = Path(os.getenv("COMSOL_AGENT_KNOWLEDGE_DB_DIR", str(PROJECT_ROOT / "knowledge_base")))
MODELS_DIR = Path(os.getenv("COMSOL_AGENT_MODELS_DIR", str(PROJECT_ROOT / "comsol_models")))
SCREENSHOT_DIR = Path(os.getenv("COMSOL_GUI_SCREENSHOT_DIR", str(PROJECT_ROOT / "screenshots")))
COMSOL_RAG_ENABLE_FORMULA_OCR = os.getenv("COMSOL_RAG_ENABLE_FORMULA_OCR", "auto").strip().lower() or "auto"
COMSOL_RAG_RENDER_VISUAL_CROPS = env_bool("COMSOL_RAG_RENDER_VISUAL_CROPS", True)
COMSOL_RAG_MAX_CHUNK_TOKENS = env_int("COMSOL_RAG_MAX_CHUNK_TOKENS", 500)
COMSOL_RAG_CHUNK_OVERLAP_TOKENS = env_int("COMSOL_RAG_CHUNK_OVERLAP_TOKENS", 80)
COMSOL_RAG_PDF_BACKEND = os.getenv("COMSOL_RAG_PDF_BACKEND", "hybrid").strip().lower() or "hybrid"
COMSOL_RAG_MINERU_MODE = os.getenv("COMSOL_RAG_MINERU_MODE", "selective").strip().lower() or "selective"
COMSOL_RAG_MINERU_COMMAND = os.getenv("COMSOL_RAG_MINERU_COMMAND", "mineru").strip() or "mineru"
COMSOL_RAG_MINERU_CACHE_DIR = Path(
    os.getenv("COMSOL_RAG_MINERU_CACHE_DIR", str(CACHE_DIR / "mineru"))
)
COMSOL_RAG_MINERU_COMPLEXITY_THRESHOLD = env_int("COMSOL_RAG_MINERU_COMPLEXITY_THRESHOLD", 3)
COMSOL_RAG_MINERU_TIMEOUT_SEC = env_float("COMSOL_RAG_MINERU_TIMEOUT_SEC", 600.0)
EMBEDDING_PROVIDER = "dashscope"
EMBEDDING_MODEL = os.getenv("COMSOL_AGENT_EMBEDDING_MODEL", "text-embedding-v4").strip() or "text-embedding-v4"
EMBEDDING_DIMENSION = env_int("COMSOL_AGENT_EMBEDDING_DIMENSION", 1024)
EMBEDDING_ENDPOINT = os.getenv(
    "COMSOL_AGENT_EMBEDDING_ENDPOINT",
    "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
).strip()
EMBEDDING_BATCH_SIZE = env_int("COMSOL_AGENT_EMBEDDING_BATCH_SIZE", 10)
EMBEDDING_TIMEOUT_SEC = env_float("COMSOL_AGENT_EMBEDDING_TIMEOUT_SEC", 60.0)
EMBEDDING_RETRY_COUNT = env_int("COMSOL_AGENT_EMBEDDING_RETRY_COUNT", 2)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()

COMSOL_PROCESS_NAMES = tuple(
    name.strip().lower()
    for name in os.getenv("COMSOL_GUI_PROCESS_NAMES", "ComsolUI.exe,comsol.exe").split(",")
    if name.strip()
)
WINDOW_TITLE_PATTERN = os.getenv("COMSOL_GUI_WINDOW_TITLE_PATTERN", "COMSOL")
JAVA_SHELL_TITLE_PATTERN = os.getenv("COMSOL_JAVA_SHELL_TITLE_PATTERN", "Java Shell")
GUI_TIMEOUT_SEC = env_float("COMSOL_GUI_TIMEOUT_SEC", 10.0)
GUI_DESCENDANT_LIMIT = env_int("COMSOL_GUI_DESCENDANT_LIMIT", 1200)
GUI_SHELL_SCAN_TIMEOUT_SEC = env_float("COMSOL_GUI_SHELL_SCAN_TIMEOUT_SEC", 8.0)
GUI_AUTO_OPEN_SHELL = env_bool("COMSOL_GUI_AUTO_OPEN_SHELL", False)
GUI_WINDOW_LIST_LIMIT = env_int("COMSOL_GUI_WINDOW_LIST_LIMIT", 20)
COMSOL_DESKTOP_EXECUTABLE = os.getenv("COMSOL_DESKTOP_EXECUTABLE", "").strip()
COMSOL_DESKTOP_WORKDIR = os.getenv("COMSOL_DESKTOP_WORKDIR", "").strip()
COMSOL_DESKTOP_ARGS = os.getenv("COMSOL_DESKTOP_ARGS", "-Dcs.3drend=sw").strip()
COMSOL_GUI_OPEN_WAIT_SEC = env_float("COMSOL_GUI_OPEN_WAIT_SEC", 90.0)
