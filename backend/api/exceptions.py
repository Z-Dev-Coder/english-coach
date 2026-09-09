"""Uniform, user-friendly API error responses.

Learners should never see a stack trace or a vendor error string. Every error
leaving the API has the same shape: {"error": {"code", "message", "detail"}}.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.ai.providers.base import AIError, AIOutputError, AIUnavailable

logger = logging.getLogger(__name__)


def _envelope(code: str, message: str, detail=None, http_status=status.HTTP_400_BAD_REQUEST):
    return Response(
        {"error": {"code": code, "message": message, "detail": detail}}, status=http_status
    )


def friendly_exception_handler(exc, context):
    """DRF exception handler, extended with our AI failure modes."""
    if isinstance(exc, AIUnavailable):
        logger.warning("AI unavailable: %s", exc)
        return _envelope(
            "ai_unavailable",
            "The local AI model is not available right now. You can keep studying: "
            "review, templates and saved lessons all work without it.",
            str(exc),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if isinstance(exc, AIOutputError):
        logger.warning("AI output rejected: %s", exc)
        return _envelope(
            "ai_bad_output",
            "The AI returned something we could not use. Please try again.",
            str(exc),
            status.HTTP_502_BAD_GATEWAY,
        )
    if isinstance(exc, AIError):
        return _envelope("ai_error", "Something went wrong with the AI request.", str(exc),
                         status.HTTP_502_BAD_GATEWAY)

    response = exception_handler(exc, context)
    if response is None:
        return None  # let Django handle it (and 500 in DEBUG with the real traceback)

    detail = response.data
    message = "Request failed."
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
    elif isinstance(detail, dict):
        message = "Some fields need fixing."
    response.data = {
        "error": {"code": f"http_{response.status_code}", "message": message, "detail": detail}
    }
    return response
