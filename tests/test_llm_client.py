"""Unit tests for llm_client.xai_endpoint resolution + helpers.

llm_client is the single source of truth for where xAI requests
get sent. A regression in `xai_endpoint`'s resolution order would
silently mis-route every xAI call across the surface.

The four behavioral branches of `xai_endpoint`:

  (a) Proxy fully configured (LLM_PROXY_BASE_URL + LLM_PROXY_API_KEY
      both set) -> returns the proxy URL + proxy key. The master
      XAI_API_KEY never leaves the proxy process.

  (b) Proxy partially configured (one of LLM_PROXY_BASE_URL or
      LLM_PROXY_API_KEY set, the other missing) -> degrades to
      the direct path rather than silently 401-ing on misconfig.

  (c) Direct only (XAI_API_KEY set, no proxy env) -> returns
      direct api.x.ai/v1 + the direct key. Production deploy
      shape with no proxy in front.

  (d) Unconfigured (no proxy env, no XAI_API_KEY) -> returns
      (None, None). Caller branches on the None return rather
      than constructing an OpenAI client with empty credentials
      that would silently 401 on first request.

Plus `xai_configured()` (boolean form for use as a gate guard)
and `xai_openai_client()` (None on unconfigured + builds the
SDK client otherwise).
"""

from typing import Any
import importlib

import pytest


@pytest.fixture
def llm_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Fresh import of llm_client with all relevant env vars
    cleared. Each test starts from "nothing configured" and sets
    only what it needs.

    Why monkeypatch.delenv with raising=False: the env vars may
    or may not be set in the test runner's process; delenv with
    raising=True would fail when running under a clean shell. The
    discipline is "for this test, those vars are unset," not
    "those vars must have been set externally."
    """
    monkeypatch.delenv("LLM_PROXY_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_PROXY_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    import llm_client as _llm_client
    importlib.reload(_llm_client)
    return _llm_client


def test_xai_endpoint_returns_proxy_when_both_proxy_env_set(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Branch (a): both LLM_PROXY_BASE_URL and LLM_PROXY_API_KEY
    set. Proxy wins regardless of whether XAI_API_KEY is also set
    (proxy > direct in the resolution order).
    """
    monkeypatch.setenv("LLM_PROXY_BASE_URL", "http://proxy.test:4000")
    monkeypatch.setenv("LLM_PROXY_API_KEY", "proxy-secret")
    monkeypatch.setenv("XAI_API_KEY", "direct-key-should-be-ignored")

    base, key = llm_client.xai_endpoint()
    assert base == "http://proxy.test:4000"
    assert key == "proxy-secret"


def test_xai_endpoint_strips_trailing_slash_from_proxy_base(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The proxy base URL gets `.rstrip("/")` so trailing slashes
    do not produce double-slash URLs downstream
    (`http://proxy/v1/chat` vs `http://proxy//v1/chat`). Pin so a
    refactor that drops the rstrip surfaces immediately.
    """
    monkeypatch.setenv("LLM_PROXY_BASE_URL", "http://proxy.test:4000/")
    monkeypatch.setenv("LLM_PROXY_API_KEY", "proxy-secret")

    base, _key = llm_client.xai_endpoint()
    assert base == "http://proxy.test:4000"
    assert not base.endswith("/")


def test_xai_endpoint_degrades_to_direct_when_proxy_key_missing(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Branch (b1): LLM_PROXY_BASE_URL set but LLM_PROXY_API_KEY
    missing. The OR-fallback shape the docstring promises: degrades
    cleanly to the direct path rather than silently breaking. A
    deployment that misconfigures the proxy half-way (e.g., sets
    base URL but forgets to push the secret) should not be silently
    broken; the direct path is the safety net.
    """
    monkeypatch.setenv("LLM_PROXY_BASE_URL", "http://proxy.test:4000")
    monkeypatch.setenv("XAI_API_KEY", "direct-fallback")

    base, key = llm_client.xai_endpoint()
    assert base == "https://api.x.ai/v1"
    assert key == "direct-fallback"


def test_xai_endpoint_degrades_to_direct_when_proxy_url_missing(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Branch (b2): inverse of the above. Proxy key set but base
    URL missing. Same OR-fallback discipline: degrades to direct.
    """
    monkeypatch.setenv("LLM_PROXY_API_KEY", "proxy-secret")
    monkeypatch.setenv("XAI_API_KEY", "direct-fallback")

    base, key = llm_client.xai_endpoint()
    assert base == "https://api.x.ai/v1"
    assert key == "direct-fallback"


def test_xai_endpoint_returns_direct_when_only_xai_key_set(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Branch (c): production-deploy shape. XAI_API_KEY set via
    deployment secrets manager, no proxy runs in front. Returns
    api.x.ai/v1 + the direct key.
    """
    monkeypatch.setenv("XAI_API_KEY", "prod-key")

    base, key = llm_client.xai_endpoint()
    assert base == "https://api.x.ai/v1"
    assert key == "prod-key"


def test_xai_endpoint_returns_none_when_nothing_configured(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Branch (d): unconfigured. (None, None) signals "do not
    call xAI" to every caller; constructing an OpenAI client with
    empty credentials would silently 401 on first request and
    break Layer A. The None return is the load-bearing safety
    valve for pipx-installed wheels where the user has no key
    configured at all.
    """
    base, key = llm_client.xai_endpoint()
    assert base is None
    assert key is None


def test_xai_endpoint_treats_empty_string_env_as_unset(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Edge case: env var set to empty string (e.g., a shell
    `export XAI_API_KEY=` without a value). The strip+truthy check
    in xai_endpoint must treat empty as unset; otherwise a
    deployment with mistakenly-cleared env produces a
    silently-401-ing client.
    """
    monkeypatch.setenv("LLM_PROXY_BASE_URL", "")
    monkeypatch.setenv("LLM_PROXY_API_KEY", "")
    monkeypatch.setenv("XAI_API_KEY", "")

    base, key = llm_client.xai_endpoint()
    assert base is None
    assert key is None


def test_xai_endpoint_treats_whitespace_only_env_as_unset(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Edge case: env var set to whitespace (a `.env` file with
    `XAI_API_KEY=  ` or accidental quoted-whitespace). The strip
    in xai_endpoint must treat whitespace-only as unset.
    """
    monkeypatch.setenv("XAI_API_KEY", "   ")

    base, key = llm_client.xai_endpoint()
    assert base is None
    assert key is None


def test_xai_configured_true_when_proxy_configured(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """xai_configured is the boolean form for use as a gate guard
    (e.g., V4.2 enable check). True when proxy path is configured.
    """
    monkeypatch.setenv("LLM_PROXY_BASE_URL", "http://proxy.test:4000")
    monkeypatch.setenv("LLM_PROXY_API_KEY", "proxy-secret")

    assert llm_client.xai_configured() is True


def test_xai_configured_true_when_only_direct_key_set(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """xai_configured returns True when ONLY direct key is set
    (proxy-only deploys would fall to the direct fallback per
    branch (b)).
    """
    monkeypatch.setenv("XAI_API_KEY", "direct-key")

    assert llm_client.xai_configured() is True


def test_xai_configured_false_when_unconfigured(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """xai_configured returns False when neither path is reachable.
    Replaces scattered bare `os.environ.get("XAI_API_KEY")` checks
    that would miss proxy-only deploys; this test pins the
    True-on-proxy-only invariant by complement.
    """
    assert llm_client.xai_configured() is False


def test_xai_openai_client_returns_none_when_unconfigured(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """xai_openai_client returns None when no path is configured.
    Callers must branch on the None return; constructing an
    OpenAI client with empty base_url or api_key would silently
    401 on first request rather than fall cleanly into Layer A.

    Verified BEFORE the import of `openai` would fire because the
    None-return short-circuits before the SDK import. A test
    environment without `openai` installed still passes this
    test.
    """
    client = llm_client.xai_openai_client()
    assert client is None


def test_xai_openai_client_constructs_when_configured(
    llm_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """xai_openai_client constructs an OpenAI SDK client when
    configured. Smoke check: the function returns a non-None
    object, the constructor receives the resolved base + key
    pair. Does not exercise the real network (the SDK construction
    is offline).

    Skipped if `openai` is not installed in the test environment;
    the discipline is "if we can construct the client, do; if not,
    None" -- the latter is covered by the prior test.
    """
    monkeypatch.setenv("XAI_API_KEY", "test-key")

    try:
        import openai  # noqa: F401
    except ImportError:
        pytest.skip("openai package not installed in test env")

    client = llm_client.xai_openai_client()
    assert client is not None
    # The OpenAI SDK exposes base_url + api_key as instance attrs
    # (the SDK normalizes them); spot-check that the resolution
    # routed correctly.
    assert "api.x.ai" in str(client.base_url)
