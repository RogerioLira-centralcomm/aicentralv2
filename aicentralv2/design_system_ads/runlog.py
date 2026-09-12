"""Log de execução da mesa Ads — passos, modelo, uso e saída. Não persiste segredo."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

MAX_TEXT = 12000
MAX_STEPS = 24


class DesignSystemRunError(ValueError):
    def __init__(self, message, run=None):
        super().__init__(message)
        self.run = run


def new_run(operation):
    return {
        "run_id": f"dsa-{uuid.uuid4().hex[:10]}",
        "operation": str(operation or "ads")[:40],
        "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "steps": [],
    }


def add_step(
    run,
    *,
    step,
    status="ok",
    model="",
    duration_ms=0,
    usage=None,
    input_text="",
    output="",
    error="",
    notes=None,
    artifact="",
    result="",
):
    data = run if isinstance(run, dict) else new_run("ads")
    steps = list(data.get("steps") or [])
    steps.append(
        {
            "id": f"step-{len(steps) + 1}",
            "step": str(step or "passo")[:40],
            "status": str(status or "ok")[:20],
            "model": str(model or "")[:80],
            "duration_ms": max(0, int(duration_ms or 0)),
            "usage": _usage(usage),
            "input": _clip(input_text),
            "output": _clip(output),
            "error": str(error or "")[:400],
            "notes": [str(item)[:200] for item in (notes or [])][:6],
            "artifact": str(artifact or "")[:300],
            "result": str(result or summarize_result(step, output, error, notes, artifact))[:160],
        }
    )
    data["steps"] = steps[-MAX_STEPS:]
    return data


def summarize_result(step, output="", error="", notes=None, artifact=""):
    if error:
        return str(error)[:160]
    parsed = _json_output(output)
    if parsed:
        copy = parsed.get("ad_copy") if isinstance(parsed.get("ad_copy"), dict) else {}
        headline = str(copy.get("headline") or "").strip()
        cta = str(copy.get("cta") or "").strip()
        if headline:
            return f"{headline} — {cta}"[:160] if cta else headline[:160]
        if "passed" in parsed:
            score = parsed.get("score")
            mark = "passou" if parsed.get("passed") else "não passou"
            return f"{mark} ({score})" if score not in (None, "") else mark
    if artifact:
        return str(artifact)[:160]
    for note in notes or []:
        if str(note).strip():
            return str(note)[:160]
    text = str(output or "").strip()
    return text[:160]


def _json_output(output):
    text = str(output or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        data = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except Exception:
            return None
    return data if isinstance(data, dict) else None


def wrap_text_callable(callable, run, step="llm"):
    if callable is None:
        return None

    def wrapped(messages, **kwargs):
        started = time.perf_counter()
        model = str(kwargs.get("model") or "")
        excerpt = messages_excerpt(messages)
        try:
            result = callable(messages, **kwargs)
        except Exception as exc:
            add_step(
                run,
                step=step,
                status="error",
                model=model,
                duration_ms=_ms(started),
                input_text=excerpt,
                error=str(exc),
            )
            raise
        payload = result if isinstance(result, dict) else {}
        content = payload.get("message", {}).get("content") if payload else result
        add_step(
            run,
            step=step,
            status="ok",
            model=str(payload.get("model") or model),
            duration_ms=_ms(started),
            usage=payload.get("usage"),
            input_text=excerpt,
            output=_content_text(content),
        )
        return result

    return wrapped


def messages_excerpt(messages):
    parts = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role") or "user"
        parts.append(f"[{role}] {_content_text(item.get('content'))}")
    return "\n\n".join(parts)


def _content_text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "image_url":
                    chunks.append("[imagem de referência]")
                else:
                    chunks.append(str(item.get("text") or "")[:2000])
            else:
                chunks.append(str(item)[:2000])
        return "\n".join(part for part in chunks if part)
    return str(content)


def _usage(usage):
    data = usage if isinstance(usage, dict) else {}
    prompt = data.get("prompt_tokens") or data.get("input_tokens")
    completion = data.get("completion_tokens") or data.get("output_tokens")
    total = data.get("total_tokens")
    cost = data.get("cost")
    out = {}
    if prompt not in (None, ""):
        out["prompt_tokens"] = prompt
    if completion not in (None, ""):
        out["completion_tokens"] = completion
    if total not in (None, ""):
        out["total_tokens"] = total
    if cost not in (None, ""):
        out["cost"] = cost
    return out


def _clip(value):
    text = str(value or "")
    if len(text) <= MAX_TEXT:
        return text
    return text[: MAX_TEXT - 20] + "\n…[cortado]"


def _ms(started):
    return int((time.perf_counter() - started) * 1000)
