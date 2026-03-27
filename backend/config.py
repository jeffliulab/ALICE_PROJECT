"""Configuration for the Generative Agents simulation."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# LLM — defaults to Ollama local inference
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:14b")

# Embedding
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Paths
DATA_DIR = Path(__file__).resolve().parent / "data"

# Debug
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
