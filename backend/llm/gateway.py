"""LLM Gateway — provider management, model listing, provider detection, health checks."""

import logging
from fastapi import APIRouter, HTTPException
from backend.config import settings

router = APIRouter()
log = logging.getLogger("llm-gateway")


@router.get("/providers")
async def list_providers():
    """List all configured LLM providers and their models."""
    providers = {}
    for name, cfg in settings.LLM_PROVIDERS.items():
        env_key = cfg.get("env_key", "")
        api_key = getattr(settings, env_key, "") if env_key else ""
        providers[name] = {
            "base_url": cfg["base_url"],
            "configured": bool(api_key) or name == "ollama",
            "models": cfg["models"],
        }
    return {"providers": providers, "default_model": settings.DEFAULT_MODEL}


@router.get("/models")
async def list_models():
    """List all available models across all providers."""
    all_models = []
    for name, cfg in settings.LLM_PROVIDERS.items():
        for model in cfg["models"]:
            all_models.append({"provider": name, "model": model})
    return {"models": all_models, "default": settings.DEFAULT_MODEL}


@router.post("/detect")
async def detect_provider(url: str):
    """Detect provider from URL."""
    for name, cfg in settings.LLM_PROVIDERS.items():
        if cfg["base_url"] in url:
            return {"provider": name, "base_url": cfg["base_url"]}
    return {"provider": "openai", "base_url": url}


@router.get("/health")
async def health_check_providers():
    """Check health of all configured LLM providers.

    Tests each provider with a minimal completion request and returns
    which ones are actually working.
    """
    import httpx

    results = {}
    for name, cfg in settings.LLM_PROVIDERS.items():
        env_key = cfg.get("env_key", "")
        api_key = getattr(settings, env_key, "") if env_key else ""

        # Skip providers that aren't configured (no API key and not ollama)
        if name != "ollama" and not api_key:
            results[name] = {
                "status": "not_configured",
                "base_url": cfg["base_url"],
                "healthy": False,
            }
            continue

        base_url = cfg["base_url"]
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # Use a minimal request — just 1 token
            # Pick first model from provider
            test_model = cfg["models"][0] if cfg["models"] else "unknown"

            payload = {
                "model": test_model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 1,
            }

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )

            if resp.status_code == 200:
                results[name] = {
                    "status": "healthy",
                    "base_url": base_url,
                    "healthy": True,
                    "model_tested": test_model,
                    "response_time_ms": None,  # Could track with perf_counter
                }
            else:
                results[name] = {
                    "status": f"error_{resp.status_code}",
                    "base_url": base_url,
                    "healthy": False,
                    "error": resp.text[:200],
                }

        except httpx.ConnectError:
            results[name] = {
                "status": "unreachable",
                "base_url": base_url,
                "healthy": False,
                "error": "Could not connect to provider",
            }
        except httpx.TimeoutException:
            results[name] = {
                "status": "timeout",
                "base_url": base_url,
                "healthy": False,
                "error": "Request timed out",
            }
        except Exception as e:
            results[name] = {
                "status": "error",
                "base_url": base_url,
                "healthy": False,
                "error": str(e)[:200],
            }

    healthy_count = sum(1 for r in results.values() if r.get("healthy"))
    return {
        "healthy_count": healthy_count,
        "total_providers": len(results),
        "providers": results,
    }
