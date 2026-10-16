"""Release checks follow README examples rather than a previous draft's locals."""

import pytest

from tools.release_probe import run_readme


def test_examples_share_state_without_prescribed_names(tmp_path, capsys):
    readme = tmp_path / "README.md"
    readme.write_text(
        "```python\nrenamed_result = [42]\nprint(renamed_result)\n```\n"
        "```python\nassert renamed_result == [42]\n```\n",
        encoding="utf-8",
    )
    assert run_readme(readme) == 2
    assert capsys.readouterr().out == ""


def test_missing_examples_are_not_a_success(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("Documentation without runnable examples", encoding="utf-8")
    with pytest.raises(ValueError, match="no Python examples"):
        run_readme(readme)


def test_broken_example_fails_the_probe(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("```python\nassert False, 'broken example'\n```\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="broken example"):
        run_readme(readme)
