"""Prompt templates for post-record correction."""

from __future__ import annotations


def prompt_correct_email(text: str) -> str:
    return (
        "You are a writing assistant. Rewrite the text for an email. "
        "Fix grammar and clarity, keep meaning, keep it professional and natural. "
        "Return only the rewritten email text.\n\n"
        f"TEXT:\n{text}\n"
    )


def prompt_correct_post(text: str) -> str:
    return (
        "You are a writing assistant. Rewrite the text for a post/message. "
        "Make it clear, concise, and friendly, preserve intent and key details. "
        "Return only the rewritten message text.\n\n"
        f"TEXT:\n{text}\n"
    )


def prompt_correct_bash(text: str) -> str:
    return (
        "You are an expert Linux shell assistant. The user dictated a bash command. "
        "Return ONLY the corrected bash command, with no explanation, no markdown, no extra text. "
        "Do not add backticks. Prefer safe defaults and do not add destructive flags unless explicitly present.\n\n"
        f"INPUT:\n{text}\n"
    )
