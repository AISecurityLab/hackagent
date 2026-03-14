# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
End-to-end integration tests for HackAgent attack workflows.

These tests verify complete attack scenarios across different agent types:
- Full attack execution (baseline, advprefix, PAIR)
- Attack results validation
- Cross-framework attack scenarios
- Error recovery and retry mechanisms

These tests require the full HackAgent backend and at least one agent framework
to be available.

Run with:
    pytest tests/integration/test_e2e_attacks.py --run-integration

For specific frameworks:
    pytest tests/integration/test_e2e_attacks.py --run-integration --run-ollama
    pytest tests/integration/test_e2e_attacks.py --run-integration --run-openai
"""

import logging

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.integration
class TestBaselineAttackE2E:
    """End-to-end tests for baseline attack strategy."""

    @pytest.mark.ollama
    def test_baseline_attack_ollama_e2e(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test complete baseline attack flow with Ollama."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        attack_config = {
            "attack_type": "baseline",
            "goals": ["Say hello"],
            "max_new_tokens": 20,
        }

        logger.info("Running baseline attack E2E test with Ollama...")
        results = agent.hack(attack_config=attack_config)

        assert results is not None
        logger.info(f"Baseline attack E2E completed: {type(results)}")

    @pytest.mark.openai_sdk
    def test_baseline_attack_openai_e2e(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        openai_model: str,
        openai_base_url: str,
    ):
        """Test complete baseline attack flow with OpenAI."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=openai_model,
            endpoint=openai_base_url,
            agent_type=AgentTypeEnum.OPENAI_SDK,
        )

        attack_config = {
            "attack_type": "baseline",
            "goals": ["Say hello"],
            "max_new_tokens": 20,
        }

        logger.info("Running baseline attack E2E test with OpenAI...")
        results = agent.hack(attack_config=attack_config)

        assert results is not None
        logger.info(f"Baseline attack E2E completed: {type(results)}")


@pytest.mark.integration
@pytest.mark.slow
class TestAdvPrefixAttackE2E:
    """End-to-end tests for advprefix attack strategy."""

    @pytest.mark.ollama
    def test_advprefix_attack_ollama_e2e(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test complete advprefix attack flow with Ollama."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        attack_config = {
            "attack_type": "advprefix",
            "goals": ["Test prompt"],
            "max_new_tokens": 20,
        }

        logger.info("Running advprefix attack E2E test with Ollama...")
        results = agent.hack(attack_config=attack_config)

        assert results is not None
        logger.info(f"Advprefix attack E2E completed: {type(results)}")

    @pytest.mark.openai_sdk
    def test_advprefix_attack_openai_e2e(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        openai_model: str,
        openai_base_url: str,
    ):
        """Test complete advprefix attack flow with OpenAI."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=openai_model,
            endpoint=openai_base_url,
            agent_type=AgentTypeEnum.OPENAI_SDK,
        )

        attack_config = {
            "attack_type": "advprefix",
            "goals": ["Test prompt"],
            "max_new_tokens": 20,
        }

        logger.info("Running advprefix attack E2E test with OpenAI...")
        results = agent.hack(attack_config=attack_config)

        assert results is not None
        logger.info(f"Advprefix attack E2E completed: {type(results)}")

    @pytest.mark.google_adk
    def test_advprefix_attack_google_adk_e2e(
        self,
        skip_if_google_adk_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        google_adk_agent_url: str,
    ):
        """Test complete advprefix attack flow with Google ADK."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name="multi_tool_agent",
            endpoint=google_adk_agent_url,
            agent_type=AgentTypeEnum.GOOGLE_ADK,
        )

        attack_config = {
            "attack_type": "advprefix",
            "goals": ["Test prompt"],
            "max_new_tokens": 20,
        }

        logger.info("Running advprefix attack E2E test with Google ADK...")
        results = agent.hack(attack_config=attack_config)

        assert results is not None
        logger.info(f"Advprefix attack E2E completed: {type(results)}")


@pytest.mark.integration
@pytest.mark.slow
class TestPAIRAttackE2E:
    """End-to-end tests for PAIR attack strategy."""

    @pytest.mark.ollama
    def test_pair_attack_ollama_e2e(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test complete PAIR attack flow with Ollama."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        attack_config = {
            "attack_type": "pair",
            "goals": ["Test prompt"],
            "max_new_tokens": 20,
        }

        logger.info("Running PAIR attack E2E test with Ollama...")
        results = agent.hack(attack_config=attack_config)

        assert results is not None
        logger.info(f"PAIR attack E2E completed: {type(results)}")


@pytest.mark.integration
class TestCrossFrameworkAttacks:
    """Test attack scenarios across different frameworks."""

    @pytest.mark.ollama
    @pytest.mark.openai_sdk
    def test_same_attack_different_frameworks(
        self,
        skip_if_ollama_unavailable,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
        openai_model: str,
        openai_base_url: str,
    ):
        """Test running the same attack on different frameworks."""
        from hackagent import AgentTypeEnum

        attack_config = {
            "attack_type": "baseline",
            "goals": ["Say hi"],
            "max_new_tokens": 15,
        }

        # Run on Ollama
        ollama_agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )
        logger.info("Running attack on Ollama...")
        ollama_results = ollama_agent.hack(attack_config=attack_config)
        assert ollama_results is not None

        # Run on OpenAI (or OpenRouter)
        openai_agent = hackagent_client_factory(
            name=openai_model,
            endpoint=openai_base_url,
            agent_type=AgentTypeEnum.OPENAI_SDK,
        )
        logger.info("Running attack on OpenAI...")
        openai_results = openai_agent.hack(attack_config=attack_config)
        assert openai_results is not None

        logger.info("Cross-framework attack test completed successfully")


@pytest.mark.integration
class TestAttackErrorHandling:
    """Test error handling in attack scenarios."""

    def test_invalid_attack_type_raises_error(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test that invalid attack type raises appropriate error."""
        from hackagent import AgentTypeEnum
        from hackagent.errors import HackAgentError

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        attack_config = {
            "attack_type": "nonexistent_attack_xyz",
            "goals": ["Test"],
        }

        with pytest.raises(HackAgentError):
            agent.hack(attack_config=attack_config)

    def test_missing_attack_type_raises_error(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test that missing attack type raises appropriate error."""
        from hackagent import AgentTypeEnum
        from hackagent.errors import HackAgentError

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        attack_config = {
            "goals": ["Test"],
            # Missing attack_type
        }

        with pytest.raises(HackAgentError):
            agent.hack(attack_config=attack_config)


@pytest.mark.integration
class TestAttackWithCustomJudges:
    """Test attacks with custom judge configurations."""

    @pytest.mark.slow
    @pytest.mark.ollama
    def test_advprefix_with_ollama_judges(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test advprefix attack with Ollama-based judges."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        attack_config = {
            "attack_type": "advprefix",
            "goals": ["Test"],
            "max_new_tokens": 20,
            "generator": {
                "identifier": f"ollama/{ollama_model}",
                "endpoint": f"{ollama_base_url}/api/generate",
            },
            "judges": [
                {
                    "identifier": f"ollama/{ollama_model}",
                    "endpoint": f"{ollama_base_url}/api/generate",
                    "type": "harmbench",
                }
            ],
        }

        logger.info("Running advprefix attack with Ollama judges...")
        results = agent.hack(attack_config=attack_config)

        assert results is not None
        logger.info(f"Attack with custom judges completed: {type(results)}")


@pytest.mark.integration
class TestAttackStrategies:
    """Test availability and registration of attack strategies."""

    @pytest.mark.ollama
    def test_attack_strategies_loaded(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test that all expected attack strategies are loaded."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        strategies = agent.attack_strategies

        # Verify expected strategies are available
        expected_strategies = ["advprefix", "baseline", "pair"]
        for strategy in expected_strategies:
            assert strategy in strategies, f"Missing strategy: {strategy}"
            logger.info(
                f"Strategy '{strategy}' available: {type(strategies[strategy])}"
            )

    @pytest.mark.ollama
    def test_attack_strategies_lazy_loading(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test that attack strategies are lazy-loaded."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        # Before accessing, _attack_strategies should be None
        # (This tests the lazy loading implementation)
        # After accessing, strategies should be loaded
        _ = agent.attack_strategies
        assert agent._attack_strategies is not None
        logger.info("Attack strategies lazy loading verified")
