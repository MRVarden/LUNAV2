"""Tests for AST runner — Python structural analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from luna.metrics.runners.ast_runner import AstRunner


@pytest.fixture
def ast_runner():
    return AstRunner()


@pytest.fixture
def python_project(tmp_path):
    """Create a minimal Python project for AST analysis."""
    src = tmp_path / "src"
    src.mkdir()

    # Source file with classes and functions
    (src / "module.py").write_text(
        '''
class MyService:
    """A sample service class."""

    def process(self, data):
        """Process data."""
        result = []
        for item in data:
            result.append(item * 2)
        return result

    def validate(self, input_data):
        """Validate input."""
        if not input_data:
            raise ValueError("empty")
        return True


def helper_function(x, y):
    """A standalone helper."""
    return x + y


def another_function():
    """Another function."""
    pass
''',
        encoding="utf-8",
    )

    # Test file
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_module.py").write_text(
        '''
def test_helper():
    assert True

def test_process():
    assert True
''',
        encoding="utf-8",
    )

    return tmp_path


class TestAstRunner:
    """Tests for AstRunner."""

    def test_properties(self, ast_runner):
        """AstRunner has correct name and language."""
        assert ast_runner.name == "ast"
        assert ast_runner.language == "python"

    @pytest.mark.asyncio
    async def test_is_available(self, ast_runner):
        """AST runner uses stdlib — always available."""
        assert await ast_runner.is_available() is True

    @pytest.mark.asyncio
    async def test_run_on_project(self, ast_runner, python_project):
        """AST runner analyzes a Python project."""
        result = await ast_runner.run(python_project)
        assert result.success is True
        assert result.runner_name == "ast"
        assert result.data["total_files"] >= 2
        assert result.data["total_classes"] >= 1
        assert result.data["total_functions"] >= 2

    @pytest.mark.asyncio
    async def test_abstraction_ratio(self, ast_runner, python_project):
        """Abstraction ratio = classes / total_entities."""
        result = await ast_runner.run(python_project)
        data = result.data
        expected = data["total_classes"] / data["total_entities"]
        assert abs(data["abstraction_ratio"] - expected) < 0.01

    @pytest.mark.asyncio
    async def test_test_ratio(self, ast_runner, python_project):
        """Test ratio counts test files vs source files."""
        result = await ast_runner.run(python_project)
        assert result.data["test_files"] >= 1
        assert result.data["source_files"] >= 1
        assert result.data["test_ratio"] > 0

    @pytest.mark.asyncio
    async def test_function_size_quality(self, ast_runner, python_project):
        """Function size quality uses phi soft constraint."""
        result = await ast_runner.run(python_project)
        quality = result.data["function_size_quality"]
        assert 0.0 <= quality <= 1.0

    @pytest.mark.asyncio
    async def test_run_on_single_file(self, ast_runner, python_project):
        """AST runner works on a single file."""
        single_file = python_project / "src" / "module.py"
        result = await ast_runner.run(single_file)
        assert result.success is True
        assert result.data["total_files"] == 1

    @pytest.mark.asyncio
    async def test_run_on_nonexistent_path(self, ast_runner):
        """AST runner handles nonexistent paths."""
        result = await ast_runner.run(Path("/nonexistent/path"))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_run_on_empty_dir(self, ast_runner, tmp_path):
        """AST runner handles empty directories."""
        result = await ast_runner.run(tmp_path)
        assert result.success is True
        assert result.data["total_files"] == 0

    @pytest.mark.asyncio
    async def test_syntax_error_handling(self, ast_runner, tmp_path):
        """AST runner handles files with syntax errors gracefully."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(:\n  pass", encoding="utf-8")
        result = await ast_runner.run(tmp_path)
        # Should succeed but with 0 entities from the broken file
        assert result.success is True
