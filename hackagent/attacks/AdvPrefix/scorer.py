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
Scoring module for AdvPrefix attacks.

This module implements various scoring mechanisms used to evaluate and rank
adversarial prefixes throughout the AdvPrefix attack pipeline. It provides
different scoring strategies based on various criteria such as attack success
rate, naturalness, and robustness.

The module provides functionality for:
- Multiple scoring algorithms and strategies
- Composite scoring with weighted criteria
- Score normalization and standardization
- Ranking and sorting based on scores
- Performance metrics calculation
- Score-based filtering and selection

Scoring is a critical component for determining the effectiveness and quality
of generated adversarial prefixes.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
    SpinnerColumn,
)
from .utils import call_litellm_completion  # Import the utility

# Configure LiteLLM logging (optional)
# litellm.set_verbose = True

logger = logging.getLogger(__name__)

# --- Configuration Classes ---


@dataclass
class ScorerConfig:
    """Base configuration for scorers"""

    model_id: str  # Identifier for the model used for scoring (litellm string)
    batch_size: int = 1  # Default to 1 for LiteLLM scorer processing
    # surrogate_attack_prompt: str = "" # Maybe needed if formatting prompts


@dataclass
class LiteLLMAPIScoreConfig(ScorerConfig):
    """Configuration specific to LiteLLM API-based scoring"""

    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    surrogate_attack_prompt: str = ""  # Prompt template if needed for API call
    logprob_token_buffer: int = (
        5  # How many extra tokens to request beyond estimated prefix length
    )
    request_timeout: int = 120  # Timeout for API calls


# --- Base Scorer Class (Optional but good practice) ---
class BaseScorer:
    """
    Abstract base class for adversarial prefix scoring implementations.

    This class defines the common interface for all scorer implementations
    used in the AdvPrefix attack pipeline. Scorers are responsible for
    evaluating the quality and effectiveness of generated adversarial prefixes
    using various metrics such as negative log-likelihood (NLL) scores.

    Attributes:
        config: ScorerConfig instance containing scorer-specific parameters
        logger: Logger instance for tracking scoring operations
    """

    def __init__(self, config: ScorerConfig):
        """
        Initialize the base scorer with the provided configuration.

        Args:
            config: ScorerConfig instance containing model identifier,
                batch size, and other scorer-specific parameters.
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def calculate_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate effectiveness scores for adversarial prefixes.

        This method must be implemented by subclasses to provide specific
        scoring algorithms for evaluating prefix quality.

        Args:
            df: DataFrame containing prefixes to score. Must include
                'goal' and 'prefix' columns.

        Returns:
            DataFrame with additional scoring columns added.

        Raises:
            NotImplementedError: This is an abstract method that must be
                implemented by concrete scorer subclasses.
        """
        raise NotImplementedError

    def __del__(self):
        """
        Clean up resources used by the scorer.

        Subclasses should override this method to properly clean up
        any resources such as model instances or API connections.
        """
        pass


class LiteLLMAPIScorer(BaseScorer):
    """
    Calculate approximate NLL scores for adversarial prefixes using LiteLLM APIs.

    This scorer uses LiteLLM-compatible APIs that support log probabilities to
    estimate negative log-likelihood scores for generated prefixes. The scores
    help identify which prefixes are most likely to be effective against
    target models.

    The scoring process involves:
    1. Formatting goals as prompts for the scoring model
    2. Requesting completions with log probability information
    3. Analyzing log probabilities to compute approximate NLL scores
    4. Handling API errors and edge cases gracefully

    Note:
        This provides approximate NLL scores and is NOT equivalent to precise
        cross-entropy calculation. The accuracy depends on the scoring model's
        log probability implementation and tokenization alignment.

    Attributes:
        config: LiteLLMAPIScoreConfig with API-specific parameters
        api_key: Retrieved API key from environment variables
    """

    def __init__(self, config: LiteLLMAPIScoreConfig):
        """
        Initialize the LiteLLM API scorer with configuration and API credentials.

        Args:
            config: LiteLLMAPIScoreConfig containing model identifier, API
                endpoints, authentication details, and scoring parameters.
        """
        super().__init__(config)
        self.config: LiteLLMAPIScoreConfig  # Type hint
        self.api_key = None
        if self.config.api_key:
            self.api_key = os.environ.get(self.config.api_key)
            if not self.api_key:
                self.logger.warning(
                    f"Environment variable {self.config.api_key} not set for API key."
                )

        self.logger.info(
            f"LiteLLMAPIScorer initialized for model {self.config.model_id}. Token counts will be estimated based on character length."
        )

    def _estimate_token_count(self, text: str) -> int:
        """
        Estimate the token count for a text string using character-based approximation.

        This method provides a rough estimate of how many tokens a text string
        will contain when processed by the scoring model. The estimation is
        used to determine appropriate max_tokens settings for API requests.

        Args:
            text: Input text string to estimate token count for.

        Returns:
            Estimated number of tokens as an integer. Uses a rough approximation
            of 4 characters per token plus 1 for safety margin.

        Note:
            This is a heuristic approximation and may not match the exact
            tokenization used by the target model. It's designed to provide
            reasonable estimates for API request sizing rather than precise
            token counting.
        """
        # Only use character-based estimation
        # Rough estimate: 4 chars per token (adjust if needed)
        count = (len(text) // 4) + 1
        # self.logger.debug(f"Estimated token count for text length {len(text)}: {count}")
        return count

    def calculate_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate approximate NLL scores for prefixes using LiteLLM API log probabilities.

        This method processes a DataFrame of adversarial prefixes and computes
        approximate negative log-likelihood scores by querying the configured
        model through LiteLLM APIs. The scores help rank prefix effectiveness.

        The scoring process for each prefix:
        1. Format the goal as a prompt (with optional surrogate attack prompt)
        2. Estimate required token count for the prefix
        3. Request completion with log probabilities enabled
        4. Extract and sum log probabilities for the prefix tokens
        5. Convert to negative log-likelihood score

        Args:
            df: DataFrame containing adversarial prefixes to score. Must include
                'goal' and 'prefix' columns. Additional columns are preserved.

        Returns:
            DataFrame with an additional 'prefix_nll' column containing the
            computed NLL scores. Failed computations are assigned infinity
            (indicating poor quality).

        Note:
            Progress tracking is provided for long-running scoring operations.
            API errors are handled gracefully with appropriate logging, and
            failed scores are set to infinity to ensure they rank poorly.

            The accuracy of scores depends on the model's log probability
            implementation and how well the tokenization aligns between
            the scoring model and the eventual target model.
        """
        self.logger.info(
            f"Calculating approximate NLL (LiteLLM) for {len(df)} prefixes using {self.config.model_id}"
        )

        result_df = df.copy()
        # Ensure column exists, default to infinity (bad score)
        if "prefix_nll" not in result_df.columns:
            result_df["prefix_nll"] = float("inf")
        else:
            result_df["prefix_nll"] = result_df["prefix_nll"].fillna(float("inf"))

        approx_nlls = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            TimeRemainingColumn(),
        ) as progress_bar:
            task = progress_bar.add_task(
                "[cyan]Calculating Approx NLL (LiteLLM)...", total=len(df)
            )
            for index, row in df.iterrows():
                goal = row["goal"]
                prefix = row["prefix"]
                current_nll = float("inf")  # Default to bad score

                try:
                    # 1. Format the goal as the prompt
                    formatted_goal = goal
                    if self.config.surrogate_attack_prompt:
                        try:
                            formatted_goal += (
                                self.config.surrogate_attack_prompt.format(prefix="")
                            )  # Still formatting here
                        except Exception as fmt_e:
                            self.logger.warning(
                                f"Failed to format surrogate prompt for goal scoring, using original. Error: {fmt_e}"
                            )

                    messages = [{"role": "user", "content": formatted_goal}]

                    # 2. Estimate prefix length and set max_tokens
                    num_prefix_tokens = self._estimate_token_count(prefix.lstrip())
                    max_tokens_to_request = (
                        num_prefix_tokens + self.config.logprob_token_buffer
                    )

                    # 3. Call the utility function requesting logprobs
                    _content, logprob_info, error = call_litellm_completion(
                        model_id=self.config.model_id,
                        messages=messages,
                        endpoint=self.config.endpoint,
                        api_key=self.api_key,
                        timeout=self.config.request_timeout,
                        temperature=0.0,  # Deterministic for scoring
                        max_tokens=max_tokens_to_request,
                        logprobs=True,  # Request logprobs
                        logger=self.logger,
                    )

                    # 4. Handle error or process logprobs
                    if error:
                        self.logger.error(
                            f"LiteLLM call failed during NLL calculation for item {index}: {error}"
                        )
                        # Keep current_nll as inf
                    elif logprob_info:
                        # Process logprobs (logic remains similar)
                        content_from_logprobs = getattr(logprob_info, "content", None)
                        if content_from_logprobs and isinstance(
                            content_from_logprobs, list
                        ):
                            returned_tokens = [
                                item.get("token") for item in content_from_logprobs
                            ]
                            returned_logprobs = [
                                item.get("logprob") for item in content_from_logprobs
                            ]
                            generated_text = "".join(
                                t for t in returned_tokens if t is not None
                            )
                            target_prefix_stripped = prefix.lstrip()

                            if generated_text.startswith(target_prefix_stripped):
                                count = 0
                                summed_logprob = 0.0
                                for tok, lp in zip(returned_tokens, returned_logprobs):
                                    if lp is None:
                                        continue
                                    summed_logprob += lp
                                    count += 1
                                    if count >= num_prefix_tokens:
                                        break
                                if count > 0:
                                    current_nll = -summed_logprob
                                else:
                                    self.logger.warning(
                                        f"Logprob alignment for item {index}: No valid logprobs found."
                                    )
                            elif (
                                target_prefix_stripped.startswith(generated_text)
                                and len(generated_text) > 0
                            ):
                                self.logger.warning(
                                    f"Logprob alignment for item {index}: API generated only '{generated_text[:50]}...' which is a prefix of target."
                                )
                                summed_logprob = sum(
                                    lp for lp in returned_logprobs if lp is not None
                                )
                                if returned_logprobs and any(
                                    lp is not None for lp in returned_logprobs
                                ):
                                    current_nll = -summed_logprob
                            else:
                                self.logger.warning(
                                    f"Logprob alignment for item {index}: Generated text '{generated_text[:50]}...' does not match target prefix '{target_prefix_stripped[:50]}...'."
                                )
                        else:
                            self.logger.warning(
                                f"Logprobs returned for item {index}, but in unexpected format: {logprob_info}"
                            )
                    else:
                        # Utility function already logs warning if logprobs requested but not found
                        pass  # Keep current_nll as inf

                except Exception as e:  # Catch errors in the calling code (e.g., formatting, estimate_token_count)
                    self.logger.error(
                        f"Error calculating approx NLL for item {index} outside LiteLLM call: {e}",
                        exc_info=True,
                    )
                    # Keep current_nll as inf

                approx_nlls.append(current_nll)
                progress_bar.update(task, advance=1)

        # Update DataFrame
        if len(approx_nlls) == len(result_df):
            result_df["prefix_nll"] = approx_nlls
        else:
            self.logger.error(
                f"Mismatch between calculated approx NLLs ({len(approx_nlls)}) and DataFrame rows ({len(result_df)}). NLL column may be incorrect."
            )
            # Pad/truncate as fallback
            if len(approx_nlls) < len(result_df):
                approx_nlls.extend([float("inf")] * (len(result_df) - len(approx_nlls)))
            result_df["prefix_nll"] = approx_nlls[: len(result_df)]

        self.logger.info(
            f"Finished calculating approximate NLL (LiteLLM) for {len(result_df)} prefixes."
        )
        return result_df

    def __del__(self):
        self.logger.info(
            "LiteLLMAPIScorer resources released (no explicit cleanup needed)."
        )
