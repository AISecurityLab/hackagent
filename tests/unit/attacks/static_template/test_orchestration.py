# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from contextlib import ExitStack
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from hackagent.agent import HackAgent
from hackagent.attacks.generator import AttackTemplates
from hackagent.errors import HackAgentError


TRANSLATIONS = {
    "goal_translated": "Résume la météo",
    "goal_foreign": "Riassumi il meteo",
}


@pytest.fixture
def public_agent():
    backend = MagicMock()
    backend._client = None
    with (
        patch("hackagent.agent.AgentRouter"),
        patch("hackagent.agent.utils.resolve_api_token", return_value=None),
    ):
        agent = HackAgent(
            name="weather-summary",
            endpoint="http://localhost:11434",
            backend=backend,
        )
    return agent


@pytest.fixture
def execution_stages(public_agent):
    orchestrator = public_agent.attack_strategies["static_template"]
    returns = {
        "_validate_default_category_classifier_requirements": None,
        "_validate_required_models_availability": None,
        "_probe_model_target": None,
        "_create_server_attack_record": str(uuid4()),
        "_create_server_run_record": str(uuid4()),
        "_execute_local_attack": [],
    }
    with ExitStack() as stack:
        stages = {
            name: stack.enter_context(
                patch.object(orchestrator, name, return_value=value)
            )
            for name, value in returns.items()
        }
        yield stages


@pytest.mark.parametrize("availability_error", [None, "Required models unavailable"])
@pytest.mark.parametrize(
    ("config", "override", "message"),
    [
        ({"template_categories": ["multi_language"]}, None, "goal_translated"),
        ({"template_categories": ["unknown"]}, None, "Unknown template category"),
        (
            {"template_categories": ["encoding"]},
            {"template_categories": ["multi_language"]},
            "goal_translated",
        ),
        (
            {
                "template_categories": ["multi_language"],
                "template_parameters": TRANSLATIONS,
            },
            {"template_parameters": {}},
            "goal_translated",
        ),
        (
            {
                "template_categories": ["multi_language"],
                "template_parameters": TRANSLATIONS,
            },
            {"template_parameters": {"goal_translated": "Résume la météo"}},
            "goal_foreign",
        ),
        (
            {"template_categories": ["encoding"]},
            {"attack_type": "baseline", "template_categories": ["unknown"]},
            "Unknown template category",
        ),
    ],
)
def test_invalid_public_config_fails_before_probes_and_records(
    public_agent, execution_stages, config, override, message, availability_error
):
    execution_stages[
        "_validate_required_models_availability"
    ].return_value = availability_error
    with pytest.raises(HackAgentError, match=message) as error:
        public_agent.hack(
            {
                "attack_type": "static_template",
                "goals": ["Summarize weather"],
                **config,
            },
            run_config_override=override,
            fail_on_run_error=False,
        )
    assert isinstance(error.value.__cause__, ValueError)
    for stage in execution_stages.values():
        stage.assert_not_called()
    public_agent.backend.create_attack.assert_not_called()
    public_agent.backend.create_run.assert_not_called()
    public_agent.backend.update_run.assert_not_called()
    public_agent.router.route_request.assert_not_called()


@pytest.mark.parametrize("in_override", [False, True])
def test_unknown_placeholder_fails_at_public_entrypoint(
    public_agent, execution_stages, in_override
):
    config = {"attack_type": "static_template", "goals": ["Summarize weather"]}
    selection = {"template_categories": ["encoding"]}
    override = selection if in_override else None
    if not in_override:
        config.update(selection)
    with (
        patch.object(AttackTemplates, "ENCODING_BYPASS", ["{unknown_placeholder}"]),
        pytest.raises(
            HackAgentError, match="Missing template parameter 'unknown_placeholder'"
        ),
    ):
        public_agent.hack(config, run_config_override=override)
    for stage in execution_stages.values():
        stage.assert_not_called()
    public_agent.backend.create_attack.assert_not_called()
    public_agent.backend.create_run.assert_not_called()
    public_agent.router.route_request.assert_not_called()


@pytest.mark.parametrize(
    ("config", "override"),
    [
        (
            {"template_categories": ["multi_language"]},
            {"template_parameters": TRANSLATIONS},
        ),
        (
            {"template_categories": ["unknown"]},
            {"template_categories": ["encoding"]},
        ),
        (
            {
                "template_categories": ["multi_language"],
                "template_parameters": {"goal_translated": ""},
            },
            {"template_parameters": TRANSLATIONS},
        ),
    ],
)
def test_valid_override_repairs_config_before_public_validation(
    public_agent, execution_stages, config, override
):
    execution_stages[
        "_validate_required_models_availability"
    ].return_value = "Required models unavailable"
    result = public_agent.hack(
        {
            "attack_type": "static_template",
            "goals": ["Summarize weather"],
            **config,
        },
        run_config_override=override,
    )
    assert result == []
    execution_stages["_validate_required_models_availability"].assert_called_once()
    execution_stages["_create_server_attack_record"].assert_not_called()
    execution_stages["_create_server_run_record"].assert_not_called()


def test_template_validation_does_not_apply_to_other_attack_types(public_agent):
    orchestrator = public_agent.attack_strategies["baseline"]
    with (
        patch(
            "hackagent.attacks.techniques.static_template.config.validate_template_config"
        ) as validate,
        patch.object(
            orchestrator, "_validate_default_category_classifier_requirements"
        ),
        patch.object(
            orchestrator,
            "_validate_required_models_availability",
            return_value="Required models unavailable",
        ) as availability,
    ):
        assert (
            public_agent.hack(
                {
                    "attack_type": "baseline",
                    "goals": ["Summarize weather"],
                    "template_categories": ["multi_language"],
                }
            )
            == []
        )
    validate.assert_not_called()
    availability.assert_called_once()
