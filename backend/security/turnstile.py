"""
security/turnstile.py
=======================
Cloudflare Turnstile bot-detection verification.

Function
--------
verify_turnstile — validate a CF Turnstile token before processing a request

Environment variables
---------------------
CF_TURNSTILE_SECRET  : Cloudflare Turnstile secret key
CF_TURNSTILE_ENABLED : "true" / "false"  (default "false")
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import HTTPException

logger = logging.getLogger("security.turnstile")

CF_TURNSTILE_SECRET  = os.getenv("CF_TURNSTILE_SECRET", "")
CF_TURNSTILE_ENABLED = os.getenv("CF_TURNSTILE_ENABLED", "false").lower() == "true"
_CF_VERIFY_URL       = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str, remote_ip: str | None = None) -> None:
    """
    Call the Cloudflare Turnstile siteverify endpoint.

    Raises HTTPException 403 if the token is missing, invalid, or the
    Cloudflare API is unreachable.

    Set CF_TURNSTILE_ENABLED=false in .env to skip this check in development.
    """
    if not CF_TURNSTILE_ENABLED:
        return

    if not token:
        raise HTTPException(status_code=403, detail="Cloudflare Turnstile token is required.")

    if not CF_TURNSTILE_SECRET:
        logger.warning("[Turnstile] CF_TURNSTILE_SECRET is not set — skipping verification.")
        return

    payload: dict[str, Any] = {"secret": CF_TURNSTILE_SECRET, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp   = await client.post(_CF_VERIFY_URL, data=payload)
            result = resp.json()
    except Exception as exc:
        logger.error("[Turnstile] Verification request failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Bot-detection service is temporarily unavailable. Please try again.",
        )

    if not result.get("success"):
        codes = result.get("error-codes", [])
        logger.warning("[Turnstile] Verification failed: %s", codes)
        raise HTTPException(status_code=403, detail=f"Bot-detection challenge failed: {codes}")
