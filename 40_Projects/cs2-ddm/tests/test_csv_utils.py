"""
Unit and integration tests for csv_utils data persistence layer.

Test strategy:
- Unit tests: mocked file I/O for isolation
- Integration tests: real CSV files with fixture cleanup
- Target: 100% coverage on critical paths
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest
import pandas as pd

# Import the module we're testing
from csv_utils import load_existing_results, save_results


# ─────────────────────────────────────────────────────────────────────────────
# UNIT TESTS (Mocked I/O)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadExistingResults:
    """Unit tests for load_existing_results() with mocked files."""

    def test_load_nonexistent_file_returns_empty_dataframe(self):
        """Loading a non-existent file should return empty DataFrame."""
        result = load_existing_results("/nonexistent/file.csv")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_load_empty_file_returns_empty_dataframe(self):
        """Loading an empty file (size 0) should return empty DataFrame."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name

        try:
            result = load_existing_results(temp_path)
            assert isinstance(result, pd.DataFrame)
            assert result.empty
        finally:
            os.unlink(temp_path)

    def test_load_csv_without_duplicate_headers(self):
        """Loading clean CSV returns all rows."""
        csv_content = """match_id,moment_timestamp,rt_visible_to_aim_ms
1,2:30,150
2,3:15,200"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = load_existing_results(temp_path)
            assert len(result) == 2
            assert list(result.columns) == ["match_id", "moment_timestamp", "rt_visible_to_aim_ms"]
        finally:
            os.unlink(temp_path)

    def test_load_csv_strips_duplicate_headers(self):
        """Loading CSV with embedded header rows strips them."""
        csv_content = """match_id,moment_timestamp,rt_visible_to_aim_ms
1,2:30,150
match_id,moment_timestamp,rt_visible_to_aim_ms
2,3:15,200"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = load_existing_results(temp_path)
            # Should have only 2 data rows, not 3 (header row stripped)
            assert len(result) == 2
            assert result.iloc[0]["match_id"] == "1"
            assert result.iloc[1]["match_id"] == "2"
        finally:
            os.unlink(temp_path)

    def test_load_csv_coerces_numeric_columns(self):
        """Loading CSV converts numeric column strings to numbers."""
        csv_content = """match_id,t0_manual_tick,t1_aim_start_tick,t2_first_hit_tick,rt_visible_to_aim_ms
1,1000,1010,1020,150"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = load_existing_results(temp_path)
            assert result["t0_manual_tick"].dtype in [int, 'int64', 'Int64']
            assert result["rt_visible_to_aim_ms"].dtype in [int, float, 'int64', 'float64']
        finally:
            os.unlink(temp_path)

    def test_load_csv_with_corrupted_encoding(self):
        """Loading file with invalid encoding should handle gracefully."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as f:
            # Write binary junk that can't be decoded as CSV
            f.write(b'\x80\x81\x82\x83\x84\x85')
            temp_path = f.name

        try:
            result = load_existing_results(temp_path)
            # Should return empty on decode error
            assert isinstance(result, pd.DataFrame)
            assert result.empty
        finally:
            os.unlink(temp_path)


class TestSaveResults:
    """Unit and integration tests for save_results()."""

    def test_save_to_new_file_creates_file(self):
        """Saving results to non-existent file should create it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "results.csv")
            results_df = pd.DataFrame({
                "match_id": ["1"],
                "moment_timestamp": ["2:30"],
                "rt_visible_to_aim_ms": [150],
            })

            save_results(results_df, output_file, match_id="1")

            assert os.path.exists(output_file)
            saved = pd.read_csv(output_file)
            assert len(saved) == 1
            assert str(saved.iloc[0]["match_id"]) == "1"
            assert saved.iloc[0]["moment_timestamp"] == "2:30"

    def test_save_appends_new_match_id_to_existing_csv(self):
        """Saving a new match_id should append to existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "results.csv")

            # First save: match_id=1, 1 row
            df1 = pd.DataFrame({
                "match_id": ["1"],
                "moment_timestamp": ["2:30"],
                "rt_visible_to_aim_ms": [150],
            })
            save_results(df1, output_file, match_id="1")

            # Verify first save
            saved_after_1 = pd.read_csv(output_file)
            assert len(saved_after_1) == 1

            # Second save: match_id=2, 1 row (should append)
            df2 = pd.DataFrame({
                "match_id": ["2"],
                "moment_timestamp": ["3:15"],
                "rt_visible_to_aim_ms": [200],
            })
            save_results(df2, output_file, match_id="2")

            # Should have 2 rows total
            saved = pd.read_csv(output_file)
            assert len(saved) == 2
            match_ids = sorted(saved["match_id"].astype(str).unique().tolist())
            assert match_ids == ["1", "2"]

    def test_save_replaces_existing_match_id(self):
        """Saving same match_id should replace old rows (idempotent)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "results.csv")

            # First save: match_id=1 with 2 rows
            df1 = pd.DataFrame({
                "match_id": ["1", "1"],
                "moment_timestamp": ["2:30", "2:45"],
                "rt_visible_to_aim_ms": [150, 160],
            })
            save_results(df1, output_file, match_id="1")

            # Second save: match_id=1 with 1 row (should replace)
            df2 = pd.DataFrame({
                "match_id": ["1"],
                "moment_timestamp": ["3:00"],
                "rt_visible_to_aim_ms": [170],
            })
            save_results(df2, output_file, match_id="1")

            # Should still have only 1 row for match_id=1
            saved = pd.read_csv(output_file)
            assert len(saved) == 1
            assert saved.iloc[0]["moment_timestamp"] == "3:00"

    def test_save_preserves_other_match_ids(self):
        """Replacing one match_id should not affect others."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "results.csv")

            # First: save match_id=1
            df1 = pd.DataFrame({
                "match_id": ["1"],
                "moment_timestamp": ["2:30"],
                "rt_visible_to_aim_ms": [150],
            })
            save_results(df1, output_file, match_id="1")

            # Then: save match_id=2
            df2 = pd.DataFrame({
                "match_id": ["2"],
                "moment_timestamp": ["3:00"],
                "rt_visible_to_aim_ms": [200],
            })
            save_results(df2, output_file, match_id="2")

            # Verify both exist
            saved_before = pd.read_csv(output_file)
            assert len(saved_before) == 2

            # Replace match_id=1 with new data
            df3 = pd.DataFrame({
                "match_id": ["1"],
                "moment_timestamp": ["2:45"],
                "rt_visible_to_aim_ms": [155],
            })
            save_results(df3, output_file, match_id="1")

            # match_id=2 should be unchanged, match_id=1 should be updated
            saved = pd.read_csv(output_file)
            assert len(saved) == 2

            match1_rows = saved[saved["match_id"].astype(str) == "1"]
            assert len(match1_rows) == 1
            assert match1_rows.iloc[0]["moment_timestamp"] == "2:45"

            match2_rows = saved[saved["match_id"].astype(str) == "2"]
            assert len(match2_rows) == 1
            assert match2_rows.iloc[0]["moment_timestamp"] == "3:00"
            assert match2_rows.iloc[0]["rt_visible_to_aim_ms"] == 200

    def test_save_handles_empty_results(self):
        """Saving empty results should not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "results.csv")
            empty_df = pd.DataFrame()

            # Should not crash
            save_results(empty_df, output_file, match_id="1")
            # File should exist but may be empty or minimal
            assert os.path.exists(output_file)

    def test_save_single_header_row_written(self):
        """Saving should result in exactly one header row in CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "results.csv")

            df = pd.DataFrame({
                "match_id": ["1"],
                "moment_timestamp": ["2:30"],
            })

            save_results(df, output_file, match_id="1")

            # Read raw file and count header-like rows
            with open(output_file, 'r') as f:
                lines = f.readlines()

            # First line should be header
            assert "match_id" in lines[0]
            # Second line should be data
            assert "1" in lines[1]
            # Should not have duplicate headers
            assert lines.count(lines[0]) == 1
