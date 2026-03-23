"""Tests for workspace scanner .aeco.yaml support."""
from __future__ import annotations

import tempfile
from pathlib import Path

from aeco.workspace_scanner.scanner import scan_workspace


class TestAecoYamlConfig:
    def test_scan_reads_aeco_yaml(self, tmp_path: Path) -> None:
        # Create a minimal workspace with .aeco.yaml
        (tmp_path / "README.md").write_text("# Test Product\nA test product for AECO.")
        (tmp_path / ".aeco.yaml").write_text(
            "name: test_product\n"
            "goals:\n"
            "  - Increase conversion rate\n"
            "  - Reduce churn\n"
            "north_star_metric: mrr\n"
            "constraints:\n"
            "  max_monthly_budget: 500\n"
            "integrations:\n"
            "  stripe: true\n"
        )

        result = scan_workspace(str(tmp_path))
        assert "aeco_config" in result
        assert result["aeco_config"]["name"] == "test_product"
        assert result["company_goals"] == ["Increase conversion rate", "Reduce churn"]
        assert result["north_star_metric"] == "mrr"
        assert result["constraints"]["max_monthly_budget"] == 500

    def test_scan_without_aeco_yaml(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Test\nNo config.")
        result = scan_workspace(str(tmp_path))
        assert "aeco_config" not in result

    def test_scan_with_aeco_yml(self, tmp_path: Path) -> None:
        """Also supports .aeco.yml extension."""
        (tmp_path / ".aeco.yml").write_text("name: test\ngoals:\n  - Goal 1\n")
        result = scan_workspace(str(tmp_path))
        assert "aeco_config" in result
        assert result["company_goals"] == ["Goal 1"]
