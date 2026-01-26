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
Refactored adversarial prefix generation module with unified class-based architecture.

This refactored version consolidates all prefix generation, preprocessing, and
cross-entropy computation into a cohesive class-based design that improves:
- Code organization and maintainability
- State management and configuration handling
- Testing and mocking capabilities
- Logging and tracking throughout the pipeline
"""

import logging
import os
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hackagent.client import AuthenticatedClient
from hackagent.router.router import AgentRouter
from hackagent.router.types import AgentTypeEnum

if TYPE_CHECKING:
    from hackagent.router.tracking import Tracker

from .config import CUSTOM_CHAT_TEMPLATES, PrefixGenerationConfig
from .utils import REFUSAL_KEYWORDS, create_progress_bar, handle_empty_input, log_errors

# ============================================================================
# MAIN PIPELINE CLASS
# ============================================================================


class PrefixGenerationPipeline:
    """
    Unified pipeline for adversarial prefix generation, preprocessing, and evaluation.

    This class encapsulates all functionality related to generating and processing
    adversarial prefixes, providing a clean interface with proper state management
    and comprehensive tracking capabilities.

    Architecture:
        - Initialization: Sets up config, logger, clients, and internal state
        - Generation: Creates raw prefixes using uncensored models
        - Preprocessing: Two-phase filtering (pattern-based, then CE-based)
        - Cross-Entropy: Tests prefixes against target agents
        - Orchestration: execute() method coordinates the full pipeline

    Key Benefits:
        - Single source of truth for configuration
        - Consistent logging throughout all operations
        - Easy to test individual components via method mocking
        - Clear method boundaries with single responsibilities
        - Stateful execution tracking for debugging

    Example:
        pipeline = PrefixGenerationPipeline(
            config=config_dict,
            logger=logger,
            client=client,
            agent_router=router
        )
        results = pipeline.execute(goals=["harmful goal 1", "harmful goal 2"])
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        client: AuthenticatedClient,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize the pipeline with configuration and dependencies.

        Args:
            config: Configuration dictionary or PrefixGenerationConfig instance
            logger: Logger for tracking execution
            client: Authenticated client for API access
            agent_router: Optional router for CE computation
        """
        # Extract tracking context BEFORE converting to dataclass (which filters unknown fields)
        self._run_id: Optional[str] = (
            config.get("_run_id") if isinstance(config, dict) else None
        )
        self._tracking_client = (
            config.get("_client") if isinstance(config, dict) else None
        )
        # Extract tracker for per-goal result tracking
        self._tracker: Optional["Tracker"] = (
            config.get("_tracker") if isinstance(config, dict) else None
        )
        # Goal index map will be built when execute() is called with goals
        self._goal_index_map: Dict[str, int] = {}

        self.config = (
            PrefixGenerationConfig.from_dict(config)
            if isinstance(config, dict)
            else config
        )
        self.logger = logger
        self.client = client
        self.agent_router = agent_router

        # Initialize internal state for tracking
        self._generation_router: Optional[AgentRouter] = None
        self._statistics: Dict[str, Any] = {
            "raw_generated": 0,
            "phase1_filtered": 0,
            "ce_computed": 0,
            "phase2_filtered": 0,
        }

        self.logger.info("PrefixGenerationPipeline initialized")

    # ========================================================================
    # PUBLIC INTERFACE
    # ========================================================================

    @handle_empty_input("Generate Prefixes", empty_result=[])
    @log_errors("Generate Prefixes")
    def execute(self, goals: List[str]) -> List[Dict]:
        """
        Execute the complete prefix generation pipeline.

        This is the main entry point that orchestrates all sub-steps:
        1. Generate raw prefixes
        2. Apply Phase 1 preprocessing
        3. Compute cross-entropy (if agent_router provided)
        4. Apply Phase 2 preprocessing

        Args:
            goals: List of target goals for prefix generation

        Returns:
            List of filtered prefix dictionaries ready for completion generation
        """
        unique_goals = list(dict.fromkeys(goals)) if goals else []

        # Build goal index map for Tracker lookups
        self._goal_index_map = {goal: idx for idx, goal in enumerate(unique_goals)}

        # Generate raw prefixes
        self.logger.info(f"Starting generation for {len(unique_goals)} unique goals")
        raw_prefixes = self._generate_raw_prefixes(unique_goals)
        self._statistics["raw_generated"] = len(raw_prefixes)

        if not raw_prefixes:
            self.logger.warning("No prefixes generated")
            return []

        # Apply Phase 1 filtering
        self.logger.info(
            f"Applying Phase 1 preprocessing to {len(raw_prefixes)} prefixes"
        )
        phase1_results = self._apply_phase1_preprocessing(raw_prefixes)
        self._statistics["phase1_filtered"] = len(phase1_results)

        if not phase1_results:
            self.logger.warning("All prefixes filtered out in Phase 1")
            return []

        # Optional CE computation and Phase 2 filtering
        if self.agent_router:
            self.logger.info(
                f"Computing cross-entropy for {len(phase1_results)} prefixes"
            )
            ce_results = self._compute_cross_entropy_scores(phase1_results)
            self._statistics["ce_computed"] = len(ce_results)

            if not ce_results:
                self.logger.warning("CE computation produced no results")
                return []

            self.logger.info(
                f"Applying Phase 2 preprocessing to {len(ce_results)} prefixes"
            )
            final_results = self._apply_phase2_preprocessing(ce_results)
            self._statistics["phase2_filtered"] = len(final_results)

            if not final_results:
                self.logger.warning("All prefixes filtered out in Phase 2")
                return []
        else:
            self.logger.info("Skipping CE computation (no agent_router provided)")
            final_results = phase1_results

        self._log_pipeline_statistics()
        return final_results

    def get_statistics(self) -> Dict[str, Any]:
        """Return execution statistics for monitoring and debugging."""
        return self._statistics.copy()

    # ========================================================================
    # GENERATION METHODS
    # ========================================================================

    def _generate_raw_prefixes(self, goals: List[str]) -> List[Dict]:
        """
        Generate raw adversarial prefixes using uncensored models.

        Handles:
        - Router initialization
        - Prompt construction
        - Both greedy and sampling generation modes
        - Result collection with metadata
        """
        if not self.config.generator:
            self.logger.error("Missing generator configuration")
            return []

        model_name = self.config.generator.get("identifier")
        if not model_name:
            self.logger.error("Missing model identifier in generator config")
            return []

        # Initialize router if needed
        if not self._generation_router:
            self._generation_router = self._initialize_generation_router()
            if not self._generation_router:
                return []

        # Construct prompts
        prompts, prompt_goals, meta_prefixes = self._construct_prompts(goals)
        if not prompts:
            self.logger.warning("No prompts constructed")
            return []

        # Generate with both modes
        results = []
        for do_sample in [False, True]:
            mode_name = "sampling" if do_sample else "greedy"
            self.logger.debug(
                f"Running {mode_name} generation for {len(prompts)} prompts"
            )

            mode_results = self._run_generation_mode(
                prompts=prompts,
                goals=prompt_goals,
                meta_prefixes=meta_prefixes,
                do_sample=do_sample,
            )
            results.extend(mode_results)

        self.logger.info(f"Generated {len(results)} raw prefixes")
        return results

    def _initialize_generation_router(self) -> Optional[AgentRouter]:
        """Initialize and configure the AgentRouter for generation."""
        try:
            endpoint = self.config.generator.get("endpoint")
            model_name = self.config.generator.get("identifier")

            # Handle API key
            api_key = self.client.token
            api_key_config = self.config.generator.get("api_key")
            if api_key_config:
                env_key = os.environ.get(api_key_config)
                api_key = env_key if env_key else api_key_config

            operational_config = {
                "name": model_name,
                "endpoint": endpoint,
                "api_key": api_key,
                "max_new_tokens": self.config.max_new_tokens,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
            }

            # Use OPENAI_SDK to avoid Pydantic serialization warnings from LiteLLM
            # Can be overridden via config.generator["agent_type"] if needed
            agent_type_str = self.config.generator.get("agent_type", "OPENAI_SDK")
            try:
                agent_type = AgentTypeEnum(agent_type_str.upper())
            except ValueError:
                self.logger.warning(
                    f"Invalid agent_type '{agent_type_str}', defaulting to OPENAI_SDK"
                )
                agent_type = AgentTypeEnum.OPENAI_SDK

            router = AgentRouter(
                client=self.client,
                name=model_name,
                agent_type=agent_type,
                endpoint=endpoint,
                adapter_operational_config=operational_config,
                metadata=operational_config.copy(),
                overwrite_metadata=True,
            )

            if not router._agent_registry:  # type: ignore
                self.logger.error("Router initialized but no agent registered")
                return None

            self.logger.debug(f"Generation router initialized for {model_name}")
            return router

        except Exception as e:
            self.logger.error(
                f"Failed to initialize generation router: {e}", exc_info=True
            )
            return None

    def _construct_prompts(
        self, goals: List[str]
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Construct formatted prompts from goals and meta-prefixes.

        Returns:
            Tuple of (prompts, corresponding_goals, corresponding_meta_prefixes)
        """
        # Handle sample count specification
        meta_prefixes = self.config.meta_prefixes
        n_samples = self.config.meta_prefix_samples

        if isinstance(n_samples, list):
            if len(meta_prefixes) != len(n_samples):
                raise ValueError(
                    "Length mismatch between meta_prefixes and meta_prefix_samples"
                )
            n_samples_list = n_samples
        else:
            n_samples_list = [n_samples] * len(meta_prefixes)

        prompts = []
        prompt_goals = []
        prompt_meta_prefixes = []

        for goal in goals:
            for meta_prefix, n_count in zip(meta_prefixes, n_samples_list):
                if n_count <= 0:
                    continue

                try:
                    # Format prompt using template
                    if meta_prefix in CUSTOM_CHAT_TEMPLATES:
                        template = CUSTOM_CHAT_TEMPLATES[meta_prefix]
                        prompt_content = template.format(content=goal)
                    else:
                        self.logger.debug(
                            f"No template for {meta_prefix}, using basic format"
                        )
                        prompt_content = f"USER: {goal}\\nASSISTANT:"

                    full_prompt = prompt_content + meta_prefix

                    # Replicate for n_count samples
                    prompts.extend([full_prompt] * n_count)
                    prompt_goals.extend([goal] * n_count)
                    prompt_meta_prefixes.extend([meta_prefix] * n_count)

                except Exception as e:
                    self.logger.error(
                        f"Error constructing prompt for goal '{goal[:30]}...': {e}"
                    )

        return prompts, prompt_goals, prompt_meta_prefixes

    def _run_generation_mode(
        self,
        prompts: List[str],
        goals: List[str],
        meta_prefixes: List[str],
        do_sample: bool,
    ) -> List[Dict]:
        """Run generation in either greedy or sampling mode."""
        results = []
        mode = "sampling" if do_sample else "greedy"
        temperature = self.config.temperature if do_sample else 1e-2

        registration_key = next(iter(self._generation_router._agent_registry.keys()))  # type: ignore

        # Log tracking context status
        if self._tracker:
            self.logger.info("📊 Generation tracking via Tracker enabled")
        else:
            self.logger.debug("Generation tracking disabled - no tracker available")

        progress_desc = f"[cyan]Generating ({mode})..."

        with create_progress_bar(progress_desc, total=len(prompts)) as (pbar, task):
            for prompt, goal, meta_prefix in zip(prompts, goals, meta_prefixes):
                request_params = {
                    "prompt": prompt,
                    "max_new_tokens": self.config.max_new_tokens,
                    "temperature": temperature,
                    "top_p": self.config.top_p,
                }

                # Always use route_request (no auto result creation)
                # Tracker handles per-goal result tracking instead
                response = self._generation_router.route_request(
                    registration_key=registration_key,
                    request_data=request_params,
                )

                generated_text = self._extract_generated_text(response, prompt, goal)
                final_prefix = meta_prefix + generated_text

                # Add trace to goal's Result via Tracker
                if self._tracker:
                    goal_index = self._goal_index_map.get(goal)
                    if goal_index is not None:
                        goal_ctx = self._tracker.get_goal_context(goal_index)
                        if goal_ctx:
                            self._tracker.add_interaction_trace(
                                ctx=goal_ctx,
                                request=request_params,
                                response={
                                    "generated_text": generated_text,
                                    "processed_response": response.get(
                                        "processed_response"
                                    ),
                                    "error_message": response.get("error_message"),
                                },
                                step_name=f"Prefix Generation ({mode})",
                                metadata={
                                    "meta_prefix": meta_prefix,
                                    "final_prefix": final_prefix,
                                    "temperature": temperature,
                                    "model_name": self.config.generator.get(
                                        "identifier"
                                    ),
                                },
                            )

                results.append(
                    {
                        "goal": goal,
                        "prefix": final_prefix,
                        "meta_prefix": meta_prefix,
                        "temperature": temperature,
                        "model_name": self.config.generator.get("identifier"),
                    }
                )

                pbar.update(task, advance=1)

        return results

    def _extract_generated_text(self, response: Dict, prompt: str, goal: str) -> str:
        """Extract and clean generated text from router response."""
        error_msg = response.get("error_message")
        if error_msg:
            error_cat = response.get("error_category", "Unknown")
            self.logger.warning(
                f"Router error for goal '{goal[:30]}...': {error_msg} ({error_cat})"
            )
            return f" [ROUTER_ERROR: {error_cat}]"

        generated = response.get("processed_response")
        if not generated:
            return " [ROUTER_NO_CONTENT]"

        # Strip prompt if echoed
        if generated.startswith(prompt):
            return generated[len(prompt) :]

        self.logger.debug("Response didn't start with prompt, using full response")
        return generated

    # ========================================================================
    # PREPROCESSING METHODS
    # ========================================================================

    def _apply_phase1_preprocessing(self, prefixes: List[Dict]) -> List[Dict]:
        """
        Apply Phase 1 preprocessing: pattern-based filtering and deduplication.

        Filters:
        - Prefixes starting with refusal patterns
        - Prefixes containing refusal patterns
        - Prefixes below minimum character length
        - Prefixes without required linebreaks
        - Duplicate prefixes (within goals)
        """
        data = prefixes

        # Apply filters sequentially
        data = self._filter_by_start_patterns(data)
        data = self._filter_by_contain_patterns(data)
        data = self._filter_by_char_length(data)

        if self.config.require_linebreak:
            data = self._filter_by_linebreak(data)

        data = self._merge_duplicates(data)

        self._log_filtering_stats(data, "Phase 1")
        return data

    def _apply_phase2_preprocessing(self, prefixes: List[Dict]) -> List[Dict]:
        """
        Apply Phase 2 preprocessing: CE-based filtering and top-k selection.

        Filters:
        - Prefixes with CE scores above threshold
        - Keeps only top-k prefixes per goal based on CE score
        """
        if not prefixes:
            return prefixes

        # Check for prefix_nll key
        if "prefix_nll" not in prefixes[0]:
            self.logger.error("Phase 2 requires 'prefix_nll' key, skipping")
            return prefixes

        data = prefixes

        # Filter by CE threshold
        if self.config.max_ce is not None:
            data = self._filter_by_ce_threshold(data)

        # Top-k selection per goal
        if self.config.n_candidates_per_goal > 0:
            data = self._select_top_k_per_goal(data)

        self._log_filtering_stats(data, "Phase 2")
        return data

    def _filter_by_start_patterns(self, data: List[Dict]) -> List[Dict]:
        """Remove prefixes starting with refusal patterns."""
        if not self.config.start_patterns:
            return data

        before = len(data)
        patterns = tuple(self.config.start_patterns)
        filtered = [
            row
            for row in data
            if not (row.get("prefix") or "").lstrip().startswith(patterns)
        ]
        removed = before - len(filtered)

        if removed > 0:
            self.logger.debug(f"Start pattern filter removed {removed} prefixes")

        return filtered

    def _filter_by_contain_patterns(self, data: List[Dict]) -> List[Dict]:
        """Remove prefixes containing refusal patterns."""
        if not self.config.contain_patterns:
            return data

        before = len(data)
        pattern = re.compile("|".join(map(re.escape, self.config.contain_patterns)))
        filtered = [row for row in data if not pattern.search(row.get("prefix") or "")]
        removed = before - len(filtered)

        if removed > 0:
            self.logger.debug(f"Contain pattern filter removed {removed} prefixes")

        return filtered

    def _filter_by_char_length(self, data: List[Dict]) -> List[Dict]:
        """Remove prefixes shorter than minimum character length."""
        if self.config.min_char_length <= 0:
            return data

        before = len(data)
        filtered = [
            row
            for row in data
            if len(row.get("prefix") or "") >= self.config.min_char_length
        ]
        removed = before - len(filtered)

        if removed > 0:
            self.logger.debug(
                f"Character length filter removed {removed} prefixes (< {self.config.min_char_length} chars)"
            )

        return filtered

    def _filter_by_linebreak(self, data: List[Dict]) -> List[Dict]:
        """Remove prefixes without internal linebreaks."""
        before = len(data)
        filtered = [
            row for row in data if "\n" in (row.get("prefix") or "").strip().strip("\n")
        ]
        removed = before - len(filtered)

        if removed > 0:
            self.logger.debug(f"Linebreak filter removed {removed} prefixes")

        return filtered

    def _filter_by_ce_threshold(self, data: List[Dict]) -> List[Dict]:
        """Remove prefixes with CE scores above threshold."""

        def parse_numeric(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                return float("inf")

        # Check if all values are infinite
        valid_scores = [
            parse_numeric(row.get("prefix_nll"))
            for row in data
            if parse_numeric(row.get("prefix_nll")) not in (float("inf"), float("-inf"))
        ]

        if len(valid_scores) == 0:
            self.logger.warning("All CE scores are infinite, skipping CE filtering")
            return data

        before = len(data)
        filtered = [
            row
            for row in data
            if parse_numeric(row.get("prefix_nll")) <= self.config.max_ce
        ]
        removed = before - len(filtered)

        if removed > 0:
            self.logger.debug(
                f"CE threshold filter removed {removed} prefixes (CE > {self.config.max_ce})"
            )

        return filtered

    def _select_top_k_per_goal(self, data: List[Dict]) -> List[Dict]:
        """Select top-k prefixes per goal based on CE score."""

        def parse_numeric(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                return float("inf")

        before = len(data)

        # Group by goal
        from collections import defaultdict

        goal_groups = defaultdict(list)
        for row in data:
            goal_groups[row.get("goal", "")].append(row)

        # Sort each group by prefix_nll and take top k
        result = []
        for goal, rows in goal_groups.items():
            sorted_rows = sorted(rows, key=lambda x: parse_numeric(x.get("prefix_nll")))
            result.extend(sorted_rows[: self.config.n_candidates_per_goal])

        removed = before - len(result)

        if removed > 0:
            self.logger.debug(
                f"Top-k selection removed {removed} prefixes (keeping top {self.config.n_candidates_per_goal} per goal)"
            )

        return result

    def _merge_duplicates(self, data: List[Dict]) -> List[Dict]:
        """Merge duplicate prefixes within goal groups."""
        from collections import defaultdict

        before = len(data)

        # Group by goal, then by prefix
        goal_groups = defaultdict(lambda: defaultdict(list))
        for row in data:
            goal = row.get("goal", "")
            prefix = row.get("prefix", "")
            goal_groups[goal][prefix].append(row)

        # Merge duplicates within each goal
        result = []
        for goal, prefix_groups in goal_groups.items():
            for prefix, rows in prefix_groups.items():
                if len(rows) == 1:
                    result.append(rows[0])
                else:
                    # Merge by combining values
                    merged = {
                        "prefix": prefix,
                        "goal": goal,
                        "model_name": ",".join(
                            str(r.get("model_name"))
                            for r in rows
                            if r.get("model_name")
                        ),
                        "meta_prefix": ",".join(
                            str(r.get("meta_prefix"))
                            for r in rows
                            if r.get("meta_prefix")
                        ),
                        "temperature": ",".join(
                            str(r.get("temperature"))
                            for r in rows
                            if r.get("temperature") is not None
                        ),
                    }
                    # Keep first prefix_nll if exists
                    if "prefix_nll" in rows[0]:
                        merged["prefix_nll"] = rows[0]["prefix_nll"]
                    result.append(merged)

        removed = before - len(result)

        if removed > 0:
            self.logger.debug(f"Deduplication removed {removed} duplicate prefixes")

        return result

    def _log_filtering_stats(self, data: List[Dict], phase_name: str):
        """Log detailed statistics about filtering results."""
        if not data:
            self.logger.info(f"{phase_name}: No prefixes remaining")
            return

        # Count prefixes per goal
        from collections import Counter

        goal_counts = Counter(row.get("goal", "") for row in data)
        counts = list(goal_counts.values())

        self.logger.info(
            f"{phase_name}: {len(data)} prefixes remaining for {len(goal_counts)} goals "
            f"(min={min(counts)}, max={max(counts)}, "
            f"avg={sum(counts) / len(counts):.1f})"
        )

    # ========================================================================
    # CROSS-ENTROPY METHODS
    # ========================================================================

    def _compute_cross_entropy_scores(self, prefixes: List[Dict]) -> List[Dict]:
        """
        Compute cross-entropy acceptability scores for prefixes.

        Tests each prefix against the target agent and assigns scores:
        - 0.0: Agent accepted and responded without refusal
        - inf: Agent refused, errored, or response contained refusal keywords
        """
        if not self.agent_router:
            self.logger.warning("No agent_router available for CE computation")
            return prefixes

        results = []
        victim_key = str(self.agent_router.backend_agent.id)

        # Log tracking context status for CE computation
        if self._tracker:
            self.logger.info("📊 CE computation tracking via Tracker enabled")
        else:
            self.logger.debug("CE computation tracking disabled - no tracker available")

        progress_desc = (
            f"[blue]Computing CE via {self.agent_router.backend_agent.agent_type}..."
        )

        with create_progress_bar(progress_desc, total=len(prefixes)) as (pbar, task):
            for record in prefixes:
                prefix_text = record.get("prefix", "")
                goal = record.get("goal", "")

                # Initialize result with default values
                result = record.copy()
                result["prefix_nll"] = float("inf")

                # Skip invalid prefixes
                if (
                    not prefix_text
                    or not isinstance(prefix_text, str)
                    or prefix_text.isspace()
                ):
                    result["error_message"] = "Empty or invalid prefix"
                    results.append(result)
                    pbar.update(task, advance=1)
                    continue

                # Always use route_request (no auto result creation)
                # Tracker handles per-goal result tracking instead
                request_data = {"prompt": prefix_text}
                response = self.agent_router.route_request(
                    registration_key=victim_key,
                    request_data=request_data,
                )

                # Evaluate response
                generated_text = response.get("generated_text")
                error_message = response.get("error_message")

                if error_message or generated_text is None:
                    result["prefix_nll"] = float("inf")
                    result["error_message"] = error_message or "No response"
                elif any(kw in generated_text.lower() for kw in REFUSAL_KEYWORDS):
                    result["prefix_nll"] = float("inf")
                    result["error_message"] = "Response contained refusal keywords"
                else:
                    result["prefix_nll"] = 0.0
                    result["error_message"] = None

                # Add trace to goal's Result via Tracker
                if self._tracker:
                    goal_index = self._goal_index_map.get(goal)
                    if goal_index is not None:
                        goal_ctx = self._tracker.get_goal_context(goal_index)
                        if goal_ctx:
                            self._tracker.add_interaction_trace(
                                ctx=goal_ctx,
                                request=request_data,
                                response={
                                    "generated_text": generated_text,
                                    "error_message": error_message,
                                    "raw_response_status": response.get(
                                        "raw_response_status"
                                    ),
                                },
                                step_name="CE Computation",
                                metadata={
                                    "prefix": prefix_text,
                                    "prefix_nll": result["prefix_nll"],
                                    "accepted": result["prefix_nll"] == 0.0,
                                },
                            )

                # Store response metadata
                result["request_payload"] = response.get("raw_request") or {
                    "prompt": prefix_text
                }
                result["response_status"] = response.get("raw_response_status")
                result["response_headers"] = response.get("raw_response_headers")
                result["response_body_raw"] = response.get("raw_response_body")

                agent_specific = response.get("agent_specific_data", {})
                if agent_specific:
                    result["events_list"] = agent_specific.get("events_list")

                results.append(result)
                pbar.update(task, advance=1)

        # Log statistics
        accepted = sum(1 for r in results if r.get("prefix_nll") == 0.0)
        self.logger.info(
            f"CE computation: {accepted}/{len(results)} prefixes accepted by target agent"
        )

        return results

    def _log_pipeline_statistics(self):
        """Log comprehensive pipeline execution statistics."""
        stats = self._statistics
        self.logger.info("=" * 60)
        self.logger.info("Pipeline Execution Statistics:")
        self.logger.info(f"  Raw generated:     {stats['raw_generated']}")
        self.logger.info(f"  Phase 1 filtered:  {stats['phase1_filtered']}")
        self.logger.info(f"  CE computed:       {stats['ce_computed']}")
        self.logger.info(f"  Phase 2 filtered:  {stats['phase2_filtered']}")

        if stats["raw_generated"] > 0:
            retention = (stats["phase2_filtered"] / stats["raw_generated"]) * 100
            self.logger.info(f"  Retention rate:    {retention:.1f}%")

        self.logger.info("=" * 60)
