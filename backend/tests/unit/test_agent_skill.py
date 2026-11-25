"""Skill Lua y prompt sin token (B5 fase 2)."""

import json
import zipfile

import pytest

from scripts.agent_prompt import build_skill_prompt
from scripts.build_agent_skill import SOURCE, build_package


def test_skill_prompt_has_no_secret_or_backend_url():
    prompt = build_skill_prompt()
    assert "frostbase" in prompt
    assert "frostbase_query.lua" in prompt
    assert "Authorization" not in prompt
    assert "http://" not in prompt
    assert "token" in prompt.lower()  # solo la regla de no mostrarlo


def test_skill_frontmatter_matches_esp_claw_spec():
    text = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    metadata = json.loads(frontmatter)
    assert metadata["name"] == "frostbase"
    assert metadata["metadata"]["manage_mode"] in {"readonly", "web", "runtime"}
    assert "utility" in metadata["metadata"]["category"]
    assert metadata["metadata"]["cap_groups"] == ["cap_lua"]


def test_build_package_includes_private_config(tmp_path):
    output = tmp_path / "frostbase-skill.zip"
    package = build_package(
        SOURCE,
        output,
        base_url="http://192.168.0.210:8050",
        token="secret-test-token",
    )
    assert package == output
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "frostbase/SKILL.md" in names
        assert "frostbase/scripts/frostbase_query.lua" in names
        assert "frostbase/private/config.txt" in names
        config = archive.read("frostbase/private/config.txt").decode()
        assert "base=http://192.168.0.210:8050" in config
        assert "token=secret-test-token" in config
        skill = archive.read("frostbase/SKILL.md").decode()
        assert "secret-test-token" not in skill
        assert "Authorization" not in skill
        script = archive.read("frostbase/scripts/frostbase_query.lua").decode()
        assert "private/config.txt" in script
        assert "endpoint no permitido" in script


def test_build_package_requires_backend_and_token(tmp_path):
    with pytest.raises(ValueError):
        build_package(SOURCE, tmp_path / "x.zip", base_url="", token="token")
    with pytest.raises(ValueError):
        build_package(
            SOURCE,
            tmp_path / "x.zip",
            base_url="http://192.168.0.210:8050",
            token="",
        )
