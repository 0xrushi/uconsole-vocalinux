"""Tests for bash_history_retriever module."""

import os
import tempfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from unittest.mock import Mock, patch

import pytest

from vocalinux.llm import bash_history_retriever as bhr
from vocalinux.llm.bash_history_retriever import (
    _BASH_HISTORY_PATH,
    _ZSH_HISTORY_PATH,
    CommandMatch,
    _load_history_commands,
    _get_retriever,
    clear_cache,
    suggest_or_fix,
)


@dataclass(frozen=True)
class _Hit:
    """Simple hit object for test retriever."""

    page_content: str


class _FakeRetriever:
    """Deterministic retriever for tests (SequenceMatcher-based)."""

    def __init__(self, commands: list[str]) -> None:
        self._commands = commands
        self.k = 1

    def invoke(self, query: str) -> list[_Hit]:
        query = query.strip()
        scored = [(SequenceMatcher(None, query, cmd).ratio(), cmd) for cmd in self._commands]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [_Hit(page_content=cmd) for _score, cmd in scored[: max(1, self.k)]]


def _prime_history_cache(bash_path: str, zsh_path: str) -> tuple[_FakeRetriever, dict[str, str]]:
    """Load history files and prepare a fake retriever for tests."""

    commands, command_dirs = _load_history_commands()
    bhr._cached_commands = commands
    bhr._cached_command_dirs = command_dirs
    return _FakeRetriever(commands), command_dirs


@pytest.fixture(autouse=True)
def clear_retriever_cache():
    """Clear cached retriever before each test."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def temp_history_dir():
    """Create temporary directory for history files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_load_history_commands_empty(temp_history_dir):
    """Test loading commands when history files don't exist."""
    # Override history paths to temp directory
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")
    zsh_path = os.path.join(temp_history_dir, "zsh_log.tsv")

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", zsh_path
    ):
        commands, command_dirs = _load_history_commands()

    assert commands == []
    assert command_dirs == {}


def test_load_history_commands_basic(temp_history_dir):
    """Test loading commands from history files."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")
    zsh_path = os.path.join(temp_history_dir, "zsh_log.tsv")

    # Create bash history file
    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la
2025-08-19T08:46:34-04:00	user@host	/home/user	true	0	git status
2025-08-19T08:46:46-04:00	user@host	/home/user	true	0	docker ps
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    # Create zsh history file
    zsh_content = """2025-10-03T14:55:49-04:00	user@host	/home/user	true	0	curl http://example.com
2025-10-03T14:55:52-04:00	user@host	/home/user	true	0	npm install
"""
    with open(zsh_path, "w", encoding="utf-8") as f:
        f.write(zsh_content)

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", zsh_path
    ):
        commands, _command_dirs = _load_history_commands()

    # Should load all 5 unique commands
    assert len(commands) == 5
    assert "ls -la" in commands
    assert "git status" in commands
    assert "docker ps" in commands
    assert "curl http://example.com" in commands
    assert "npm install" in commands


def test_load_history_commands_deduplication(temp_history_dir):
    """Test that duplicate commands are removed."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    # Create history with duplicate commands
    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la
2025-08-19T08:46:34-04:00	user@host	/home/user	true	0	ls -la
2025-08-19T08:46:46-04:00	user@host	/home/user	true	0	git status
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        commands, _command_dirs = _load_history_commands()

    # Should deduplicate - only 2 unique commands
    assert len(commands) == 2
    assert commands.count("ls -la") == 1
    assert "git status" in commands


def test_load_history_commands_ignores_empty(temp_history_dir):
    """Test that empty commands are ignored."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    # Create history with empty lines and commands
    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la

2025-08-19T08:46:34-04:00	user@host	/home/user	true	0	git status
2025-08-19T08:46:46-04:00	user@host	/home/user	true	0	
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        commands, _command_dirs = _load_history_commands()

    # Should ignore empty commands
    assert len(commands) == 2
    assert "ls -la" in commands
    assert "git status" in commands


def test_exact_match_in_history(temp_history_dir):
    """Test that exact match returns history command."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la
2025-08-19T08:46:34-04:00	user@host	/home/user	true	0	git status
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    mock_llm = Mock(return_value=("LLM fallback result", 123))

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        fake_retriever, command_dirs = _prime_history_cache(bash_path, "/nonexistent")
        with patch(
            "vocalinux.llm.bash_history_retriever._get_retriever",
            return_value=(fake_retriever, command_dirs),
        ):
            result = suggest_or_fix(
                "ls -la", mock_llm, current_dir="/home/user", k=1, thr=0.70
            )

    assert isinstance(result, CommandMatch)
    assert result.command == "ls -la"
    assert result.from_history is True
    assert result.from_same_directory is True
    assert result.directory == "/home/user"
    mock_llm.assert_not_called()


def test_close_match_above_threshold(temp_history_dir):
    """Test that close match above threshold returns history command."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	git status
2025-08-19T08:46:34-04:00	user@host	/home/user	true	0	docker compose up
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    mock_llm = Mock(return_value=("LLM fallback result", 123))

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        fake_retriever, command_dirs = _prime_history_cache(bash_path, "/nonexistent")
        with patch(
            "vocalinux.llm.bash_history_retriever._get_retriever",
            return_value=(fake_retriever, command_dirs),
        ):
            result = suggest_or_fix(
                "git stat", mock_llm, current_dir="/home/user", k=1, thr=0.70
            )

    # "git stat" is 83% similar to "git status" - should use history
    assert isinstance(result, CommandMatch)
    assert result.command == "git status"
    assert result.from_history is True
    assert result.from_same_directory is True
    mock_llm.assert_not_called()


def test_low_match_below_threshold(temp_history_dir):
    """Test that low similarity below threshold falls back to LLM."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la
2025-08-19T08:46:34-04:00	user@host	/home/user	true	0	git status
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    mock_llm = Mock(return_value=("sudo pacman -Syu", 123))

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        fake_retriever, command_dirs = _prime_history_cache(bash_path, "/nonexistent")
        with patch(
            "vocalinux.llm.bash_history_retriever._get_retriever",
            return_value=(fake_retriever, command_dirs),
        ):
            result = suggest_or_fix(
                "install package", mock_llm, current_dir="/home/user", k=1, thr=0.70
            )

    # Very low similarity, should use LLM
    assert isinstance(result, CommandMatch)
    assert result.command == "sudo pacman -Syu"
    assert result.from_history is False
    mock_llm.assert_called_once_with("install package", "/home/user")


def test_empty_history_falls_back_to_llm(temp_history_dir):
    """Test that empty history falls back to LLM."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    mock_llm = Mock(return_value=("docker ps", 123))

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        fake_retriever, command_dirs = _prime_history_cache(bash_path, "/nonexistent")
        with patch(
            "vocalinux.llm.bash_history_retriever._get_retriever",
            return_value=(fake_retriever, command_dirs),
        ):
            result = suggest_or_fix(
                "docker ps", mock_llm, current_dir="/home/user", k=1, thr=0.70
            )

    # Should use LLM when history is empty
    assert isinstance(result, CommandMatch)
    assert result.command == "docker ps"
    assert result.from_history is False
    mock_llm.assert_called_once_with("docker ps", "/home/user")


def test_empty_query_handling(temp_history_dir):
    """Test that empty queries are handled gracefully."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    mock_llm = Mock(return_value=("LLM result", 123))

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        fake_retriever, command_dirs = _prime_history_cache(bash_path, "/nonexistent")
        with patch(
            "vocalinux.llm.bash_history_retriever._get_retriever",
            return_value=(fake_retriever, command_dirs),
        ):
            result = suggest_or_fix("", mock_llm, current_dir="/home/user", k=1, thr=0.70)

    # Should return empty string for empty query
    assert isinstance(result, CommandMatch)
    assert result.command == ""
    mock_llm.assert_not_called()


def test_whitespace_query_handling(temp_history_dir):
    """Test that whitespace-only queries are handled gracefully."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    mock_llm = Mock(return_value=("LLM result", 123))

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        fake_retriever, command_dirs = _prime_history_cache(bash_path, "/nonexistent")
        with patch(
            "vocalinux.llm.bash_history_retriever._get_retriever",
            return_value=(fake_retriever, command_dirs),
        ):
            result = suggest_or_fix("   ", mock_llm, current_dir="/home/user", k=1, thr=0.70)

    # Should return whitespace string as-is
    assert isinstance(result, CommandMatch)
    assert result.command == "   "
    mock_llm.assert_not_called()


def test_clear_cache(temp_history_dir):
    """Test that cache clearing works."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        # First call - loads from file
        _get_retriever()
        clear_cache()

        # Second call - should reload from file after cache clear
        retriever, _command_dirs = _get_retriever()

    # Should have a retriever even after clearing cache
    assert retriever is not None


def test_get_retriever_caching(temp_history_dir):
    """Test that retriever is cached between calls."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        retriever1, command_dirs1 = _get_retriever()
        retriever2, command_dirs2 = _get_retriever()

    # Should return same cached instance
    assert retriever1 is retriever2
    assert command_dirs1 is command_dirs2


def test_bash_and_zsh_combined(temp_history_dir):
    """Test that bash and zsh history are combined."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")
    zsh_path = os.path.join(temp_history_dir, "zsh_log.tsv")

    bash_content = """2025-08-19T08:46:31-04:00	user@host	/home/user	true	0	ls -la
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    zsh_content = """2025-10-03T14:55:49-04:00	user@host	/home/user	true	0	docker ps
"""
    with open(zsh_path, "w", encoding="utf-8") as f:
        f.write(zsh_content)

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", zsh_path
    ):
        commands, _command_dirs = _load_history_commands()

    # Should load commands from both files
    assert len(commands) == 2
    assert "ls -la" in commands
    assert "docker ps" in commands


def test_directory_boost_can_cross_threshold(temp_history_dir):
    """Test that same-directory similarity boost can change the decision."""
    bash_path = os.path.join(temp_history_dir, "bash_log.tsv")

    bash_content = """2025-08-19T08:46:31-04:00\tuser@host\t/home/user\ttrue\t0\tgit status
"""
    with open(bash_path, "w", encoding="utf-8") as f:
        f.write(bash_content)

    mock_llm = Mock(return_value=("LLM fallback result", 123))

    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        fake_retriever, command_dirs = _prime_history_cache(bash_path, "/nonexistent")
        with patch(
            "vocalinux.llm.bash_history_retriever._get_retriever",
            return_value=(fake_retriever, command_dirs),
        ):
            # Without boost, "git st" vs "git status" is 0.75 similarity.
            # With boost, it becomes 0.85 and should clear thr=0.80.
            result_same_dir = suggest_or_fix(
                "git st", mock_llm, current_dir="/home/user", k=1, thr=0.80
            )

    assert isinstance(result_same_dir, CommandMatch)
    assert result_same_dir.command == "git status"
    assert result_same_dir.from_history is True
    assert result_same_dir.from_same_directory is True
    mock_llm.assert_not_called()

    mock_llm2 = Mock(return_value=("LLM fallback result", 123))
    with patch("vocalinux.llm.bash_history_retriever._BASH_HISTORY_PATH", bash_path), patch(
        "vocalinux.llm.bash_history_retriever._ZSH_HISTORY_PATH", "/nonexistent"
    ):
        fake_retriever, command_dirs = _prime_history_cache(bash_path, "/nonexistent")
        with patch(
            "vocalinux.llm.bash_history_retriever._get_retriever",
            return_value=(fake_retriever, command_dirs),
        ):
            result_other_dir = suggest_or_fix(
                "git st", mock_llm2, current_dir="/tmp", k=1, thr=0.80
            )

    assert isinstance(result_other_dir, CommandMatch)
    assert result_other_dir.command == "LLM fallback result"
    assert result_other_dir.from_history is False
    assert result_other_dir.from_same_directory is False
    mock_llm2.assert_called_once_with("git st", "/tmp")
