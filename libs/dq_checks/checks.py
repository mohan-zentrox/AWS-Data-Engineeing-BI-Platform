"""Data quality check functions for Project Quarry.

Used by the Airflow DAG's DQ gate task (airflow/dags/sales_orders_pipeline.py)
to validate data between the clean and curated zones. Each check is a pure
function over a pandas DataFrame (or a plain list-of-dicts, for the
schema check) and returns a DQResult — never raises for a *failed* check,
only for genuinely invalid input (e.g. a missing column argument). Callers
decide whether a failed DQResult should fail the pipeline via
`run_checks(..., raise_on_failure=True)` or `assert_passed`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


class DataQualityError(RuntimeError):
    """Raised when one or more DQ checks fail and the caller asked to enforce them."""

    def __init__(self, results: Sequence["DQResult"]):
        self.results = [r for r in results if not r.passed]
        message = "; ".join(f"{r.check_name}: {r.message}" for r in self.results)
        super().__init__(f"Data quality checks failed: {message}")


@dataclass
class DQResult:
    check_name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def _require_dataframe(df: Any, check_name: str) -> None:
    if pd is None:  # pragma: no cover
        raise RuntimeError("pandas is required for dq_checks; install libs/dq_checks/requirements.txt")
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{check_name} requires a pandas DataFrame, got {type(df)!r}")


def check_schema_match(
    df: "pd.DataFrame",
    expected_schema: Mapping[str, str],
    allow_extra_columns: bool = False,
) -> DQResult:
    """Verify the DataFrame has exactly the expected columns with compatible dtypes.

    `expected_schema` maps column name -> a pandas dtype "kind" string, one of
    "int", "float", "object" (string), "bool", "datetime". Compatibility is
    checked via `pandas.api.types` "is_*_dtype" helpers so e.g. int32 vs
    int64 both satisfy "int".
    """
    _require_dataframe(df, "check_schema_match")
    from pandas.api.types import (
        is_bool_dtype,
        is_datetime64_any_dtype,
        is_float_dtype,
        is_integer_dtype,
        is_object_dtype,
        is_string_dtype,
    )

    kind_checks = {
        "int": is_integer_dtype,
        "float": is_float_dtype,
        "object": lambda s: is_object_dtype(s) or is_string_dtype(s),
        "bool": is_bool_dtype,
        "datetime": is_datetime64_any_dtype,
    }

    missing = [c for c in expected_schema if c not in df.columns]
    extra = [] if allow_extra_columns else [c for c in df.columns if c not in expected_schema]

    mismatched: dict[str, str] = {}
    for col, expected_kind in expected_schema.items():
        if col in missing:
            continue
        checker = kind_checks.get(expected_kind)
        if checker is None:
            raise ValueError(f"Unknown expected dtype kind {expected_kind!r} for column {col!r}")
        if not checker(df[col]):
            mismatched[col] = f"expected {expected_kind}, got {df[col].dtype}"

    passed = not missing and not extra and not mismatched
    details = {"missing_columns": missing, "extra_columns": extra, "dtype_mismatches": mismatched}
    message = "schema matches" if passed else f"schema mismatch: {details}"
    return DQResult("check_schema_match", passed, message, details)


def check_null_rate(df: "pd.DataFrame", column: str, max_null_rate: float = 0.0) -> DQResult:
    """Verify the fraction of nulls in `column` does not exceed `max_null_rate` (0.0-1.0)."""
    _require_dataframe(df, "check_null_rate")
    if column not in df.columns:
        return DQResult(
            "check_null_rate", False, f"column {column!r} not found in DataFrame", {"column": column}
        )
    if len(df) == 0:
        return DQResult("check_null_rate", True, "empty DataFrame, vacuously passes", {"column": column, "null_rate": 0.0})

    null_rate = float(df[column].isna().mean())
    passed = null_rate <= max_null_rate
    details = {"column": column, "null_rate": null_rate, "max_null_rate": max_null_rate}
    message = (
        f"null rate {null_rate:.4f} within threshold {max_null_rate:.4f}"
        if passed
        else f"null rate {null_rate:.4f} exceeds threshold {max_null_rate:.4f}"
    )
    return DQResult("check_null_rate", passed, message, details)


def check_uniqueness(df: "pd.DataFrame", columns: str | Sequence[str]) -> DQResult:
    """Verify there are no duplicate rows across `columns` (a single key or composite key)."""
    _require_dataframe(df, "check_uniqueness")
    cols = [columns] if isinstance(columns, str) else list(columns)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return DQResult(
            "check_uniqueness", False, f"columns not found: {missing}", {"missing_columns": missing}
        )

    dup_mask = df.duplicated(subset=cols, keep=False)
    dup_count = int(dup_mask.sum())
    passed = dup_count == 0
    details = {"columns": cols, "duplicate_row_count": dup_count, "total_rows": len(df)}
    message = "no duplicates" if passed else f"{dup_count} duplicate rows on {cols}"
    return DQResult("check_uniqueness", passed, message, details)


def check_referential_integrity(
    df: "pd.DataFrame",
    column: str,
    reference_values: "pd.DataFrame | Iterable[Any]",
    reference_column: str | None = None,
    allow_nulls: bool = True,
) -> DQResult:
    """Verify every non-null value of `column` exists in a reference value set.

    `reference_values` can be a pandas Series/DataFrame (with `reference_column`
    naming which column holds the valid values) or any iterable of valid values.
    """
    _require_dataframe(df, "check_referential_integrity")
    if column not in df.columns:
        return DQResult(
            "check_referential_integrity",
            False,
            f"column {column!r} not found in DataFrame",
            {"column": column},
        )

    if pd is not None and isinstance(reference_values, pd.DataFrame):
        if reference_column is None:
            raise ValueError("reference_column is required when reference_values is a DataFrame")
        valid_values = set(reference_values[reference_column].dropna().unique())
    else:
        valid_values = set(reference_values)

    series = df[column]
    if allow_nulls:
        series = series.dropna()

    orphaned_mask = ~series.isin(valid_values)
    orphaned_count = int(orphaned_mask.sum())
    passed = orphaned_count == 0
    details = {
        "column": column,
        "orphaned_row_count": orphaned_count,
        "orphaned_sample": series[orphaned_mask].unique().tolist()[:10],
    }
    message = "all values found in reference set" if passed else f"{orphaned_count} orphaned values in {column!r}"
    return DQResult("check_referential_integrity", passed, message, details)


def run_checks(results: Sequence[DQResult], raise_on_failure: bool = True) -> list[DQResult]:
    """Aggregate a batch of DQResult objects, optionally raising DataQualityError."""
    if raise_on_failure and any(not r.passed for r in results):
        raise DataQualityError(results)
    return list(results)
