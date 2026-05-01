"""LLM endpoint resolution for xAI/Grok calls.

Single source of truth for "where do we send Grok requests?" Two paths:

  1. LiteLLM proxy (preferred). When LLM_PROXY_BASE_URL and
     LLM_PROXY_API_KEY are set, every xAI call routes through the
     local secrets-vault LiteLLM proxy at 127.0.0.1:4000. The master
     XAI_API_KEY lives only inside the proxy process; frame-check
     never sees it. Honors the secrets-vault proxy_isolated class.

  2. Direct xAI fallback. When the proxy env is unset but
     XAI_API_KEY is set, falls back to api.x.ai/v1 directly. Used
     by prod (Fly secrets set XAI_API_KEY) and by any deploy that
     does not run a LiteLLM proxy in front.

Resolution order: proxy > direct > unconfigured. The OR-fallback
shape means a misconfigured proxy (e.g., LLM_PROXY_BASE_URL set but
LLM_PROXY_API_KEY missing) cleanly degrades to direct rather than
silently breaking analysis.

This module is imported wherever frame-check builds an OpenAI-SDK
client for xAI, plus the V4.2 engine which uses urllib directly.
"""

import os
from typing import Optional, Tuple


def xai_endpoint() -> Tuple[Optional[str], Optional[str]]:
    """Return (base_url, api_key) for xAI calls, or (None, None).

    Proxy first, direct second. (None, None) when neither path is
    configured, which signals "do not call xAI" to every caller and
    keeps Layer A as the sole framing analysis.
    """
    proxy_url = os.environ.get("LLM_PROXY_BASE_URL", "").strip()
    proxy_key = os.environ.get("LLM_PROXY_API_KEY", "").strip()
    if proxy_url and proxy_key:
        return proxy_url.rstrip("/"), proxy_key
    direct_key = os.environ.get("XAI_API_KEY", "").strip()
    if direct_key:
        return "https://api.x.ai/v1", direct_key
    return None, None


def xai_configured() -> bool:
    """True iff some xAI call path (proxy or direct) is reachable.

    Replaces the bare ``os.environ.get("XAI_API_KEY")`` checks scattered
    across app.py and the engine modules so that proxy-only deploys
    do not see V4.2 disabled despite having a valid path.
    """
    base, key = xai_endpoint()
    return bool(base and key)


def xai_openai_client():
    """Build an OpenAI-SDK client for xAI calls.

    Returns None when no xAI path is configured. Callers must branch on
    the None return; constructing an OpenAI client with empty base_url
    or api_key would silently 401 on first request rather than fall
    cleanly into Layer A.
    """
    base, key = xai_endpoint()
    if not (base and key):
        return None
    from openai import OpenAI
    return OpenAI(api_key=key, base_url=base)
