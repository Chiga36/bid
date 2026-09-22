"""Unit test for the Theme Review agent's one deterministic piece: mapping each of the seven
Theme enum values to a real, existing prompt file. No Azure OpenAI credentials needed — this
never calls the model."""
from pathlib import Path

from app.agents.theme_review import prompt_file_for_theme
from app.config import settings
from app.models import Theme


def test_every_theme_maps_to_a_distinct_prompt_file():
    filenames = {prompt_file_for_theme(theme) for theme in Theme}
    assert len(filenames) == len(list(Theme)), "every theme must map to its own distinct file"


def test_every_mapped_prompt_file_actually_exists():
    for theme in Theme:
        path: Path = settings.prompts_dir / prompt_file_for_theme(theme)
        assert path.is_file(), f"missing prompt file for {theme}: {path}"
