# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Result aggregation module for AdvPrefix attacks.

This module handles the aggregation and consolidation of results from multiple
stages of the AdvPrefix attack pipeline. It combines data from different
processing steps and provides unified result formatting.

The module provides functionality for:
- Merging results from multiple pipeline stages
- Statistical aggregation and summary calculations
- Data validation and consistency checking
- Result formatting for output and reporting
- Cross-validation of intermediate results

Aggregated results provide a comprehensive view of attack performance and
enable downstream analysis and selection processes.
"""

import pandas as pd
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Map judge type to expected column prefix/name used for aggregation stats
JUDGE_AGG_COLUMN_MAP = {
    "nuanced": "eval_nj",
    "jailbreakbench": "eval_jb",
    "harmbench": "eval_hb",
}

GROUP_KEYS = ["goal", "prefix"]


def _filter_by_nll(df: pd.DataFrame, max_ce_threshold: float | None) -> pd.DataFrame:
    """
    Filter DataFrame rows based on cross-entropy (negative log-likelihood) threshold.

    This function removes rows where the prefix_nll (cross-entropy score) exceeds
    the specified threshold, effectively filtering out prefixes that are unlikely
    to be effective based on their cross-entropy scores.

    Args:
        df: Input DataFrame containing prefix evaluation data.
            Expected to have a 'prefix_nll' column with cross-entropy scores.
        max_ce_threshold: Maximum allowed cross-entropy threshold. Rows with
            prefix_nll values greater than or equal to this threshold will be
            filtered out. If None, no filtering is performed.

    Returns:
        A filtered DataFrame with rows where prefix_nll < max_ce_threshold.
        Returns the original DataFrame if threshold is None or filtering fails.

    Note:
        Cross-entropy filtering helps remove low-quality prefixes that are
        unlikely to succeed in adversarial attacks, focusing analysis on
        the most promising candidates.
    """
    if max_ce_threshold is None:
        return df

    if "prefix_nll" not in df.columns:
        logger.warning(
            "Column 'prefix_nll' not found. Skipping NLL filtering in aggregation step."
        )
        return df

    try:
        initial_count = len(df)
        filtered_df = df[df["prefix_nll"] < max_ce_threshold]
        filtered_count = len(filtered_df)
        logger.info(
            f"Filtered {initial_count - filtered_count} rows based on prefix_nll >= {max_ce_threshold}"
        )
        return filtered_df
    except Exception as e:
        logger.error(f"Error during NLL filtering in aggregation: {e}")
        return df


def _get_available_judge_agg_cols(
    df: pd.DataFrame, config_judges: list[str]
) -> Dict[str, str]:
    """
    Identify available judge evaluation columns in the DataFrame for aggregation.

    This function checks which judge evaluation columns are present in the DataFrame
    and maps them to their corresponding judge types. It also logs warnings for
    expected judges that are missing from the results.

    Args:
        df: Input DataFrame to check for judge evaluation columns.
        config_judges: List of judge types that were expected to be run,
            used for validation and warning generation.

    Returns:
        A dictionary mapping judge type (str) to its corresponding evaluation
        column name (str) found in the DataFrame. Only includes judges that
        have their evaluation columns present in the data.

    Note:
        The function uses JUDGE_AGG_COLUMN_MAP to map judge types to their
        expected column names (e.g., "nuanced" -> "eval_nj").
    """
    available_judges_agg_cols = {}
    for judge_type, col_name in JUDGE_AGG_COLUMN_MAP.items():
        if col_name in df.columns:
            available_judges_agg_cols[judge_type] = col_name
        elif judge_type in config_judges:
            logger.warning(
                f"Expected aggregation column '{col_name}' for judge '{judge_type}' not found in the dataframe."
            )
    return available_judges_agg_cols


def _build_agg_funcs(
    base_agg_funcs: Dict[str, pd.NamedAgg],
    df: pd.DataFrame,
    available_judges_agg_cols: Dict[str, str],
) -> Dict[str, pd.NamedAgg]:
    """
    Build aggregation functions dictionary for pandas groupby operations.

    This function creates a comprehensive set of aggregation functions by starting
    with base aggregations and adding judge-specific aggregations (mean, count, size)
    for each available judge evaluation column.

    Args:
        base_agg_funcs: Dictionary of base aggregation functions (NamedAgg objects)
            to include in the final aggregation set.
        df: Input DataFrame used to validate column properties and data types.
        available_judges_agg_cols: Dictionary mapping judge types to their
            corresponding evaluation column names in the DataFrame.

    Returns:
        A comprehensive dictionary of aggregation functions (NamedAgg objects)
        ready for use with pandas groupby.agg(). Includes base aggregations
        plus mean and count aggregations for numeric judge columns.

    Note:
        The function handles numeric conversion of judge columns and gracefully
        handles non-numeric data by providing size aggregations as fallbacks.
        Mean and count aggregations are only added for columns with valid
        numeric data after type coercion.
    """
    agg_funcs = base_agg_funcs.copy()
    for judge_type, col_name in available_judges_agg_cols.items():
        try:
            # Ensure the column is numeric before calculating mean
            # This modification will be applied to a copy, not the original df passed to `execute`
            # if the original df needs to be modified, it should be done explicitly.
            numeric_col = pd.to_numeric(df[col_name], errors="coerce")
            if (
                numeric_col.notna().any()
            ):  # Check if there are any numeric values after coercion
                agg_funcs[f"{col_name}_mean"] = pd.NamedAgg(
                    column=col_name, aggfunc="mean"
                )
                agg_funcs[f"{col_name}_count"] = pd.NamedAgg(
                    column=col_name, aggfunc="count"
                )
                logger.debug(
                    f"Added mean/count aggregation for numeric column '{col_name}'"
                )
            else:
                logger.warning(
                    f"Column '{col_name}' for judge '{judge_type}' contains no numeric data after coercion. Skipping mean/count aggregation."
                )
                # Optionally, still add a size aggregation if mean/count are skipped
                agg_funcs[f"{col_name}_size"] = pd.NamedAgg(
                    column=col_name, aggfunc="size"
                )

        except KeyError:
            logger.warning(
                f"Column '{col_name}' unexpectedly missing during aggregation setup for judge '{judge_type}'. Skipping."
            )
        except Exception as e:
            logger.error(
                f"Could not process column '{col_name}' for aggregation for judge '{judge_type}'. Skipping mean/count. Error: {e}"
            )
            agg_funcs[f"{col_name}_size"] = pd.NamedAgg(column=col_name, aggfunc="size")
    return agg_funcs


def execute(
    input_df: pd.DataFrame, config: Dict[str, Any], run_dir: str
) -> pd.DataFrame:
    """
    Aggregate evaluation results from different judges using the input DataFrame.

    This function takes a DataFrame of evaluation results, filters it based on
    a cross-entropy threshold (if specified in the config), identifies available
    judge scores, and then groups by 'goal' and 'prefix' to calculate aggregate
    statistics like mean and count for each judge, along with other metadata.

    Args:
        input_df: The DataFrame containing evaluation results. Expected to have columns
                  for 'goal', 'prefix', and various judge scores (e.g., 'eval_nj').
        config: A dictionary containing configuration parameters, such as 'max_ce'
                for NLL filtering and a list of 'judges' that were expected to run.
        run_dir: The directory path for the current run (currently unused in this function
                 but part of the expected signature).

    Returns:
        A pandas DataFrame with aggregated results. Each row represents a unique
        'goal' and 'prefix' combination, with columns for aggregated scores and counts.
        Returns the unaggregated DataFrame (or an empty one with expected columns)
        if critical errors occur or if the input is empty.
    """
    logger.info("Executing Step 8: Aggregating evaluation results")

    if input_df.empty:
        logger.warning("Step 8 received an empty DataFrame. Skipping aggregation.")
        cols = GROUP_KEYS + [
            "prefix_nll",
            "model_name",
            "meta_prefix",
            "temperature",
            "n_eval_samples",
        ]
        for _, col_base in JUDGE_AGG_COLUMN_MAP.items():
            cols.extend([f"{col_base}_mean", f"{col_base}_count"])
        return pd.DataFrame(columns=cols)

    analysis_df = input_df.copy()

    max_ce_threshold = config.get("max_ce")
    if max_ce_threshold is not None:
        try:
            max_ce_threshold = float(max_ce_threshold)
        except ValueError:
            logger.warning(
                f"'max_ce' value '{max_ce_threshold}' is not a valid float. Skipping NLL filtering."
            )
            max_ce_threshold = None
    analysis_df = _filter_by_nll(analysis_df, max_ce_threshold)

    config_judges = config.get("judges", [])
    available_judges_agg_cols = _get_available_judge_agg_cols(
        analysis_df, config_judges
    )

    if not available_judges_agg_cols:
        logger.error(
            "No recognized evaluation result columns found for aggregation. Check step 7 output."
        )
        return analysis_df

    logger.info(
        f"Found aggregation columns for judges: {list(available_judges_agg_cols.keys())}"
    )

    if not all(key in analysis_df.columns for key in GROUP_KEYS):
        missing_keys = [key for key in GROUP_KEYS if key not in analysis_df.columns]
        logger.error(
            f"Missing required grouping keys for aggregation: {missing_keys}. Cannot aggregate."
        )
        return analysis_df

    base_agg_funcs = {
        "prefix_nll": pd.NamedAgg(column="prefix_nll", aggfunc="first"),
        "model_name": pd.NamedAgg(column="model_name", aggfunc="first"),
        "meta_prefix": pd.NamedAgg(column="meta_prefix", aggfunc="first"),
        "temperature": pd.NamedAgg(column="temperature", aggfunc="first"),
        "n_eval_samples": pd.NamedAgg(column=GROUP_KEYS[0], aggfunc="size"),
    }

    # Create a copy of analysis_df for modifications specific to aggregation setup
    # to avoid SettingWithCopyWarning if _build_agg_funcs modifies it.
    # The numeric conversion is now inside _build_agg_funcs and operates on a temporary series.
    agg_funcs_to_use = _build_agg_funcs(
        base_agg_funcs, analysis_df.copy(), available_judges_agg_cols
    )

    # Ensure all columns used in NamedAgg exist in analysis_df before aggregation
    for agg_name, named_agg in agg_funcs_to_use.items():
        if named_agg.column not in analysis_df.columns:
            logger.warning(
                f"Column '{named_agg.column}' for aggregation '{agg_name}' not found in DataFrame. Removing this aggregation."
            )
            # We need to remove this from the dictionary to avoid error during .agg()
            # This is tricky because we are iterating over it.
            # A better approach might be to rebuild the dict or check before adding.
            # For now, let's rely on the checks within _build_agg_funcs and assume
            # base_agg_funcs columns are either present or their absence is acceptable (e.g. 'first' on a missing col yields NaT/NaN)

    try:
        # Filter out aggregations whose columns are not in analysis_df, except for 'size' which can operate on any column.
        final_agg_funcs = {
            name: agg
            for name, agg in agg_funcs_to_use.items()
            if agg.column in analysis_df.columns or agg.aggfunc == "size"
        }

        # Also ensure all columns in GROUP_KEYS are present
        if not all(key in analysis_df.columns for key in GROUP_KEYS):
            present_keys = [key for key in GROUP_KEYS if key in analysis_df.columns]
            if not present_keys:
                logger.error(
                    "None of the GROUP_KEYS are present in the DataFrame. Cannot group."
                )
                return analysis_df  # Or raise an error
            logger.warning(
                f"Not all GROUP_KEYS are present. Grouping by available keys: {present_keys}"
            )
            current_group_keys = present_keys
        else:
            current_group_keys = GROUP_KEYS

        if not final_agg_funcs:
            logger.error(
                "No valid aggregation functions remaining after column checks. Cannot aggregate."
            )
            return analysis_df

        grouped = analysis_df.groupby(current_group_keys, observed=False, dropna=False)
        aggregated_df = grouped.agg(**final_agg_funcs)
        aggregated_df = aggregated_df.reset_index()
    except Exception as e:
        logger.error(
            f"Error during aggregation: {e}. Check aggregation functions and column types."
        )
        return analysis_df

    logger.info(
        f"Step 8 complete. Aggregated {len(aggregated_df)} prefix results. CSV will be saved by the main pipeline."
    )

    return aggregated_df
