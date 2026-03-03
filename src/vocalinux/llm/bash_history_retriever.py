"""BM25-based bash command history retrieval.

This module provides intelligent bash command correction by searching
shell command history before falling back to LLM generation.
Supports directory-aware command suggestions with PWD context.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable, Iterable, Protocol

from langchain_community.retrievers import BM25Retriever

logger = logging.getLogger(__name__)

# History file paths
_BASH_HISTORY_PATH = os.path.expanduser("~/.bash_command_log.tsv")
_ZSH_HISTORY_PATH = os.path.expanduser("~/.zsh_command_log.tsv")

# Global cached retriever
_cached_retriever: _Retriever | None = None
_cached_commands: list[str] = []
_cached_command_dirs: dict[str, str] = {}  # command -> directory mapping


@dataclass(frozen=True)
class _TextHit:
    """Minimal wrapper to mimic a retriever hit."""

    page_content: str


class _Retriever(Protocol):
    """Protocol for retrievers used by this module."""

    k: int

    def get_relevant_documents(self, query: str) -> list[_TextHit]: ...


class _SimilarityRetriever:
    """Fallback retriever using direct string similarity."""

    def __init__(self, commands: Iterable[str]) -> None:
        self._commands = [cmd for cmd in commands if cmd]
        self.k = 1

    def get_relevant_documents(self, query: str) -> list[_TextHit]:
        """Return top-k similar commands by SequenceMatcher."""

        query = query.strip()
        if not query or not self._commands:
            return []

        scored = [(SequenceMatcher(None, query, cmd).ratio(), cmd) for cmd in self._commands]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [_TextHit(page_content=cmd) for _score, cmd in scored[: max(1, self.k)]]


@dataclass
class CommandMatch:
    """Represents a command match with metadata."""

    command: str
    directory: str | None
    similarity: float
    from_history: bool
    from_same_directory: bool
    total_tokens: int | None = None


def _load_history_commands() -> tuple[list[str], dict[str, str]]:
    """Load commands and their directories from bash and zsh history files.

    Returns:
        Tuple of (commands list, command->directory mapping).
    """
    commands: list[str] = []
    command_dirs: dict[str, str] = {}
    history_files = [_BASH_HISTORY_PATH, _ZSH_HISTORY_PATH]

    for history_path in history_files:
        if not os.path.exists(history_path):
            logger.debug(f"History file not found: {history_path}")
            continue

        try:
            with open(history_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Parse TSV format (tab-separated), either:
                    # - 6 columns: time, user@host, cwd, ok, exit_code, command
                    # - 7+ columns: time, user@host, cwd, ok, exit_code, <reserved>, command
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        directory = parts[2].strip()  # cwd is field 3 (0-based index 2)
                        command = parts[6].strip()  # command is field 7 (0-based index 6)
                    elif len(parts) >= 6:
                        directory = parts[2].strip()  # cwd is field 3 (0-based index 2)
                        command = parts[5].strip()  # command is field 6 (0-based index 5)
                    else:
                        continue

                    if command and command not in command_dirs:
                        commands.append(command)
                        command_dirs[command] = directory

        except (IOError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to read history file {history_path}: {e}")

    logger.info(f"Loaded {len(commands)} unique commands from history")
    return commands, command_dirs


def _get_retriever() -> tuple[_Retriever, dict[str, str]]:
    """Get or create cached BM25 retriever and command directories.

    Returns:
        Tuple of (retriever instance, command->directory mapping).
    """
    global _cached_retriever, _cached_commands, _cached_command_dirs

    if _cached_retriever is None:
        _cached_commands, _cached_command_dirs = _load_history_commands()

        if not _cached_commands:
            _cached_retriever = _SimilarityRetriever([])
            return _cached_retriever, _cached_command_dirs

        try:
            _cached_retriever = BM25Retriever.from_texts(_cached_commands)
            _cached_retriever.k = 1
        except ImportError as e:
            logger.warning(
                "BM25 backend unavailable (%s). Falling back to similarity-only retrieval.",
                e,
            )
            _cached_retriever = _SimilarityRetriever(_cached_commands)  # type: ignore[assignment]

    return _cached_retriever, _cached_command_dirs


def _retrieve_hits(retriever: _Retriever, query: str) -> list[_TextHit]:
    """Retrieve hits using the available retriever API."""

    if hasattr(retriever, "get_relevant_documents"):
        return retriever.get_relevant_documents(query)  # type: ignore[no-any-return]
    if hasattr(retriever, "invoke"):
        return retriever.invoke(query)  # type: ignore[no-any-return]
    if callable(retriever):
        return retriever(query)  # type: ignore[no-any-return]
    raise RuntimeError("Retriever does not support expected retrieval methods")


def suggest_or_fix(
    query: str,
    llm_fallback: Callable[[str, str | None], tuple[str, int | None]],
    current_dir: str | None = None,
    k: int = 1,
    thr: float = 0.70,
) -> CommandMatch:
    """Suggest or fix bash command using BM25 history search with LLM fallback.

    First attempts to find a matching command from shell history using BM25 retrieval.
    Boosts matches from the same directory (+0.1 similarity, capped at 1.0). If a close
    match is found (similarity >= threshold), returns a CommandMatch. Otherwise, falls
    back to LLM-based correction.

    Args:
        query: The spoken/typed bash command to correct.
        llm_fallback: Callable that takes (query, current_dir) and returns an
                      LLM-corrected command.
        current_dir: Current working directory for context-aware suggestions.
        k: Number of top matches to retrieve from BM25.
        thr: Similarity threshold (0.0-1.0) for accepting history match.
              Higher = stricter matching. Default 0.70.

    Returns:
        CommandMatch with corrected command and metadata.
    """
    if not query or not query.strip():
        return _make_match(query, None, 1.0, False, False)

    query = query.strip()

    current_dir = current_dir or os.getcwd()

    # Get retriever and command directories (cached)
    retriever, command_dirs = _get_retriever()
    retriever.k = max(1, k)

    # Check if we have any history
    global _cached_commands
    if not _cached_commands:
        logger.debug("No history available, using LLM fallback")
        return _make_llm_match(llm_fallback, query, current_dir)

    # Perform BM25 search
    try:
        hits = _retrieve_hits(retriever, query)
    except Exception as e:
        logger.warning(f"BM25 search failed: {e}, falling back to LLM")
        return _make_llm_match(llm_fallback, query, current_dir)

    if not hits:
        logger.debug(f"No BM25 matches for query: {query}")
        return _make_llm_match(llm_fallback, query, current_dir)

    best_match: tuple[str, str | None, bool] | None = None
    best_similarity = 0.0

    for hit in hits[:k]:
        cmd = hit.page_content
        cmd_dir = command_dirs.get(cmd)

        similarity = SequenceMatcher(None, query, cmd).ratio()
        from_same_dir = bool(cmd_dir and cmd_dir == current_dir)
        if from_same_dir:
            similarity = min(similarity + 0.1, 1.0)

        logger.debug(
            f"BM25 match: query='{query}' cmd='{cmd}' dir='{cmd_dir}' "
            f"similarity={similarity:.2f} same_dir={from_same_dir}"
        )

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = (cmd, cmd_dir, from_same_dir)

    if best_match and best_similarity >= thr:
        cmd, cmd_dir, from_same_dir = best_match
        logger.info(
            f"Using history command (similarity={best_similarity:.2f}, same_dir={from_same_dir}): {cmd}"
        )
        return _make_match(cmd, cmd_dir, best_similarity, True, from_same_dir)

    logger.info(
        f"Similarity {best_similarity:.2f} below threshold {thr}, using LLM fallback"
    )
    return _make_llm_match(llm_fallback, query, current_dir)


def _make_match(
    command: str,
    directory: str | None,
    similarity: float,
    from_history: bool,
    from_same_directory: bool,
    total_tokens: int | None = None,
) -> CommandMatch:
    """Build a CommandMatch with consistent defaults."""

    return CommandMatch(
        command=command,
        directory=directory,
        similarity=similarity,
        from_history=from_history,
        from_same_directory=from_same_directory,
        total_tokens=total_tokens,
    )


def _make_llm_match(
    llm_fallback: Callable[[str, str | None], tuple[str, int | None]],
    query: str,
    current_dir: str | None,
) -> CommandMatch:
    """Run LLM fallback and wrap the result in a CommandMatch."""

    llm_result, total_tokens = llm_fallback(query, current_dir)
    return _make_match(llm_result, None, 0.0, False, False, total_tokens)


def clear_cache() -> None:
    """Clear the cached retriever and commands.

    Useful for testing or when history files change.
    """
    global _cached_retriever, _cached_commands, _cached_command_dirs
    _cached_retriever = None
    _cached_commands = []
    _cached_command_dirs = {}
