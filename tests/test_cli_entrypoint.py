from __future__ import annotations

import sys
import unittest
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def load_pyproject() -> dict:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))


class CliEntrypointTests(unittest.TestCase):
    def test_package_installs_codex_limit_patch_command(self) -> None:
        data = load_pyproject()

        self.assertEqual(
            data["project"]["scripts"]["codex_limit_patch"],
            "codex_limit_patch.cli:main",
        )
        self.assertEqual(
            data["project"]["scripts"]["codex_limit_patch_overlay"],
            "codex_limit_patch.overlay:main",
        )
        self.assertEqual(
            data["project"]["scripts"]["ai_usage_monitor_demo"],
            "codex_limit_patch.usage_monitor.three_source_demo:main",
        )
        self.assertEqual(
            data["project"]["scripts"]["ai_usage_monitor_menubar"],
            "codex_limit_patch.usage_monitor.macos_menubar:main",
        )

    def test_macos_menu_bar_dependency_is_optional(self) -> None:
        data = load_pyproject()

        self.assertEqual(
            data["project"]["optional-dependencies"]["macos-menubar"],
            ["rumps>=0.4,<1"],
        )

    def test_package_discovery_only_includes_runtime_package(self) -> None:
        data = load_pyproject()

        self.assertEqual(
            data["tool"]["setuptools"]["packages"]["find"]["include"],
            ["codex_limit_patch*"],
        )


if __name__ == "__main__":
    unittest.main()
