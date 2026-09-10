"""Agentes da Modelagem: contrato único, GPT via OpenRouter."""

from .contract import PieceContract
from .models import AGENT_MODELS
from .orchestrator import run_agent

__all__ = ["PieceContract", "AGENT_MODELS", "run_agent"]
