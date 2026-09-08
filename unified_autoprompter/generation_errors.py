"""Console-safe failure summaries. Never echo provider bodies or user inputs."""
import logging
import re

PROVIDER_LABELS = {
    "gemini": "Gemini", "grok": "Grok", "deepseek": "DeepSeek",
    "openai": "OpenAI Compatible", "lm_studio": "LM Studio",
    "unsloth": "Unsloth Studio", "ollama": "Ollama", "local": "Local GGUF",
}


class ProviderHTTPError(ValueError):
    """Only a safe summary and HTTP status survive the adapter boundary."""

    def __init__(self, status: int, detail: str, backend: str):
        self.http_status = int(status)
        safe = friendly_error(ValueError(f"HTTP {status}: {detail}"), backend)
        self.safe_summary = safe
        super().__init__(safe)


def friendly_error(error: Exception, backend: str) -> str:
    if isinstance(error, ProviderHTTPError):
        return error.safe_summary
    text = str(error).lower()
    match = re.search(r"(?:http|api)\s+(\d{3})\b|^(\d{3})\b", text)
    status = int(next(value for value in match.groups() if value)) if match else None
    if any(word in text for word in ("content_policy", "content policy", "content_filter", "content filter", "safety violation", "safety policy", "usage guideline", "moderation", "policy violation", "content rejected", "content blocked", "potentially sensitive content", "inappropriate content", "prohibited content")):
        advice = "The provider rejected this request under its content or safety rules. This is not an API-key error."
    elif any(word in text for word in ("insufficient_quota", "insufficient credits", "available credits", "spending limit", "billing", "credit balance")):
        advice = "The provider's billing or credit limit was reached. Check your account credits and spending limits."
    elif status == 401 or any(word in text for word in ("invalid api key", "incorrect api key", "no xai api key", "invalid_api_key", "unauthorized", "authentication failed")):
        advice = "Authentication failed. Check the API key or server access settings."
    elif status == 403 or "permission denied" in text:
        advice = "The provider denied access to this request. Check model/team permissions; the API key may still be valid."
    elif status == 429 or "rate limit" in text:
        advice = "The provider is busy or its usage limit was reached. Wait and check your provider quota."
    elif any(word in text for word in ("out of memory", "cuda allocation", "failed to allocate", "not enough memory")):
        advice = "There is not enough memory. Reduce context or output tokens, or increase CPU offloading."
    elif any(word in text for word in ("context length", "context window", "context size", "too many tokens", "maximum context")):
        advice = "The request exceeds the model context. Reduce the input or increase supported context settings."
    elif any(word in text for word in ("mmproj", "vision", "does not accept image", "image input")):
        advice = "The model cannot use these images. Select a vision model and, for Local GGUF, a compatible mmproj."
    elif any(word in text for word in ("timed out", "timeout")):
        advice = "Generation timed out. Check the server and increase Timeout if needed."
    elif any(word in text for word in ("connection", "connecterror", "unreachable", "name resolution")):
        advice = "The server could not be reached. Check its address and that it is running."
    elif any(word in text for word in ("model not found", "model_not_found", "no model", "404", "gguf model", "failed to load model")):
        advice = "The model is unavailable. Refresh the model list and select an available model."
    elif status in {400, 422}:
        advice = "The provider rejected the request parameters. Check the selected model and supported generation settings."
    else:
        advice = "Generation failed. Check the selected model and provider settings, then try again."
    http = f" (HTTP {status})" if status else ""
    return f"{PROVIDER_LABELS.get(backend, 'Provider')}{http}: {advice} Previous output kept."


def log_generation_error(error: Exception, backend: str) -> str:
    message = friendly_error(error, backend)
    logging.getLogger("workflowx.unified").warning(message)
    return message
