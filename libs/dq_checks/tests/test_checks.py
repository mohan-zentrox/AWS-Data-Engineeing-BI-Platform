from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dq_checks.checks import (  # noqa: E402
    DataQualityError,
    check_null_rate,
    check_referential_integrity,
    check_schema_match,
    check_uniqueness,
    run_checks,
)


@pytest.fixture
def sales_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": ["SO-1001", "SO-1002", "SO-1003"],
            "customer_id": ["C-01", "C-02", "C-03"],
            "order_amount": [100.0, 250.5, 75.25],
            "quantity": [1, 2, 3],
        }
    )


# ---------------------------------------------------------------------------
# check_schema_match
# ---------------------------------------------------------------------------


def test_schema_match_passes_for_matching_schema(sales_df):
    expected = {
        "order_id": "object",
        "customer_id": "object",
        "order_amount": "float",
        "quantity": "int",
    }
    result = check_schema_match(sales_df, expected)
    assert result.passed
    assert result.details["missing_columns"] == []
    assert result.details["extra_columns"] == []


def test_schema_match_fails_for_missing_column(sales_df):
    expected = {"order_id": "object", "region": "object"}
    result = check_schema_match(sales_df, expected, allow_extra_columns=True)
    assert not result.passed
    assert "region" in result.details["missing_columns"]


def test_schema_match_fails_for_dtype_mismatch(sales_df):
    expected = {"order_amount": "int"}
    result = check_schema_match(sales_df, expected, allow_extra_columns=True)
    assert not result.passed
    assert "order_amount" in result.details["dtype_mismatches"]


def test_schema_match_flags_unexpected_extra_columns(sales_df):
    expected = {"order_id": "object"}
    result = check_schema_match(sales_df, expected, allow_extra_columns=False)
    assert not result.passed
    assert set(result.details["extra_columns"]) == {"customer_id", "order_amount", "quantity"}


# ---------------------------------------------------------------------------
# check_null_rate
# ---------------------------------------------------------------------------


def test_null_rate_passes_when_no_nulls(sales_df):
    result = check_null_rate(sales_df, "order_id", max_null_rate=0.0)
    assert result.passed


def test_null_rate_fails_above_threshold():
    df = pd.DataFrame({"col": [1, None, None, 4]})
    result = check_null_rate(df, "col", max_null_rate=0.1)
    assert not result.passed
    assert result.details["null_rate"] == 0.5


def test_null_rate_passes_within_threshold():
    df = pd.DataFrame({"col": [1, None, 3, 4]})
    result = check_null_rate(df, "col", max_null_rate=0.5)
    assert result.passed


def test_null_rate_missing_column_fails():
    df = pd.DataFrame({"col": [1, 2]})
    result = check_null_rate(df, "missing_col", max_null_rate=0.0)
    assert not result.passed


def test_null_rate_empty_dataframe_vacuously_passes():
    df = pd.DataFrame({"col": pd.Series(dtype="float64")})
    result = check_null_rate(df, "col", max_null_rate=0.0)
    assert result.passed


# ---------------------------------------------------------------------------
# check_uniqueness
# ---------------------------------------------------------------------------


def test_uniqueness_passes_for_unique_key(sales_df):
    result = check_uniqueness(sales_df, "order_id")
    assert result.passed
    assert result.details["duplicate_row_count"] == 0


def test_uniqueness_fails_for_duplicate_key():
    df = pd.DataFrame({"order_id": ["A", "A", "B"]})
    result = check_uniqueness(df, "order_id")
    assert not result.passed
    assert result.details["duplicate_row_count"] == 2


def test_uniqueness_supports_composite_key():
    df = pd.DataFrame(
        {
            "order_id": ["A", "A", "B"],
            "product_sku": ["X", "Y", "X"],
        }
    )
    result = check_uniqueness(df, ["order_id", "product_sku"])
    assert result.passed


# ---------------------------------------------------------------------------
# check_referential_integrity
# ---------------------------------------------------------------------------


def test_referential_integrity_passes_with_iterable_reference(sales_df):
    result = check_referential_integrity(sales_df, "customer_id", ["C-01", "C-02", "C-03", "C-04"])
    assert result.passed


def test_referential_integrity_fails_for_orphaned_value(sales_df):
    result = check_referential_integrity(sales_df, "customer_id", ["C-01", "C-02"])
    assert not result.passed
    assert result.details["orphaned_row_count"] == 1
    assert "C-03" in result.details["orphaned_sample"]


def test_referential_integrity_supports_dataframe_reference(sales_df):
    ref_df = pd.DataFrame({"customer_id": ["C-01", "C-02", "C-03"]})
    result = check_referential_integrity(sales_df, "customer_id", ref_df, reference_column="customer_id")
    assert result.passed


def test_referential_integrity_ignores_nulls_by_default():
    df = pd.DataFrame({"customer_id": ["C-01", None]})
    result = check_referential_integrity(df, "customer_id", ["C-01"])
    assert result.passed


def test_referential_integrity_counts_nulls_when_not_allowed():
    df = pd.DataFrame({"customer_id": ["C-01", None]})
    result = check_referential_integrity(df, "customer_id", ["C-01"], allow_nulls=False)
    assert not result.passed


# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------


def test_run_checks_raises_data_quality_error_on_failure(sales_df):
    results = [
        check_null_rate(sales_df, "order_id", max_null_rate=0.0),
        check_uniqueness(pd.DataFrame({"order_id": ["A", "A"]}), "order_id"),
    ]
    with pytest.raises(DataQualityError):
        run_checks(results, raise_on_failure=True)


def test_run_checks_returns_results_when_not_raising():
    results = [check_null_rate(pd.DataFrame({"order_id": ["A", "A"]}), "order_id", 0.0)]
    returned = run_checks(results, raise_on_failure=False)
    assert returned == results
