"""Schema-driven campaign builder: fields, draft document, outline."""

import yaml

from hackagent.interfaces.tui.views.campaign.draft import CampaignDraft
from hackagent.interfaces.tui.views.campaign.outline import build_outline
from hackagent.interfaces.tui.views.campaign.schema import (
    MISSING,
    attack_fields,
    model_fields,
)
from hackagent.models.config import ModelConfig
from hackagent.orchestrator.campaign.spec import ExecutionSpec


def test_default_draft_is_a_runnable_campaign() -> None:
    spec, issues = CampaignDraft().validate()

    assert issues == ()
    assert spec is not None
    assert [attack.name for attack in spec.attacks] == ["baseline"]


def test_fields_carry_schema_defaults_and_requirements() -> None:
    fields = {field.path: field for field in model_fields(ModelConfig)}

    assert fields[("name",)].default is MISSING
    assert fields[("connection", "type")].kind == "choice"
    assert "OPENAI_SDK" in fields[("connection", "type")].choices
    assert fields[("connection", "timeout")].default == 120.0
    assert fields[("generation", "thinking")].kind == "tristate"
    # Mappings have no form row.
    assert ("connection", "headers") not in fields


def test_nested_section_fields_are_inlined() -> None:
    paths = {field.path for field in model_fields(ExecutionSpec)}

    assert ("concurrency", "target") in paths
    assert ("output", "formats") in paths


def test_a_panel_boxes_its_nested_models() -> None:
    """Grouping follows the schema: one box per nested model, in one panel."""
    from hackagent.interfaces.tui.views.campaign.schema import field_groups

    groups = field_groups(ExecutionSpec)
    own = next(group for group in groups if not group.path)
    boxed = {group.title: group for group in groups if group.path}

    assert ("mode",) in {field.path for field in own.fields}
    # A constrained optional (`Optional[Annotated[float, Gt]]`) still has a row.
    assert ("per_attack_timeout",) in {field.path for field in own.fields}
    assert set(boxed) == {"Concurrency", "Retries", "Output", "Storage"}
    assert ("concurrency", "target") in {
        field.path for field in boxed["Concurrency"].fields
    }
    storage = {field.path[-1]: field for field in boxed["Storage"].fields}
    assert storage["backend"].default == "auto"
    assert storage["backend"].choices == ("auto", "local", "remote")


def test_an_optional_nested_model_is_a_box_you_can_switch_on() -> None:
    from hackagent.interfaces.tui.views.campaign.schema import field_groups
    from hackagent.orchestrator.campaign.spec import CampaignDatasetSpec

    boxes = {group.title: group for group in field_groups(CampaignDatasetSpec)}

    assert list(boxes) == ["Source", "Selection", "Classifier"]
    assert boxes["Classifier"].optional is True
    assert boxes["Source"].optional is False


def test_every_attack_parameter_is_shown() -> None:
    """Parameters used to be cut at a fixed count, so whether one was hidden
    depended on where it happened to be declared."""
    fields = attack_fields("tap")

    from hackagent.attacks.techniques.registry import get_attack_class

    params = get_attack_class("tap").params_type
    expected = set(params.model_fields) - set(params.role_names())
    assert {field.path[-1] for field in fields} == expected
    assert not any(field.advanced for field in fields)
    assert all(field.path[0] == "parameters" for field in fields)
    assert "attacker" not in {field.path[-1] for field in fields}


def test_deleting_a_value_prunes_emptied_mappings_below_the_panel() -> None:
    draft = CampaignDraft()
    draft.delete(("dataset", "selection", "limit"), keep=1)

    assert draft.get(("dataset", "selection")) == (False, None)
    # Pruning the emptied mapping must not disturb its siblings.
    assert draft.get(("dataset", "source", "name")) == (True, "harmbench")


def test_set_reports_no_change_for_the_same_value() -> None:
    draft = CampaignDraft()

    assert draft.set(("dataset", "selection", "limit"), 10) is False
    assert draft.set(("dataset", "selection", "limit"), 5) is True


def test_missing_required_role_is_reported_on_the_role() -> None:
    draft = CampaignDraft()
    draft.append(("attacks",), {"name": "tap"})

    spec, issues = draft.validate()

    assert spec is None
    assert any(issue.loc == ("attacks", 1, "roles", "attacker") for issue in issues)


def test_bad_attack_parameter_is_reported_on_its_field() -> None:
    draft = CampaignDraft()
    draft.set(("attacks", 0), {"name": "tap", "parameters": {"depth": 0}})

    _, issues = draft.validate()

    assert any(issue.loc == ("attacks", 0, "parameters", "depth") for issue in issues)


def test_saved_yaml_contains_only_what_was_set_in_schema_order() -> None:
    draft = CampaignDraft({"attacks": [{"name": "baseline"}], "version": 1})

    assert list(yaml.safe_load(draft.to_yaml())) == ["version", "attacks"]


def test_outline_follows_the_draft_shape() -> None:
    draft = CampaignDraft()
    draft.append(("attacks",), {"name": "tap"})

    outline = {item.node.title: item for item in build_outline(draft)}
    attacks = outline["Attacks"].children

    assert [child.node.kind for child in attacks] == ["attack", "attack", "add_attack"]
    tap_roles = [child.node for child in attacks[1].children]
    assert [(role.title, role.optional) for role in tap_roles] == [
        ("attacker", False),
        ("on_topic", True),
    ]


def test_plan_counts_inline_goals() -> None:
    draft = CampaignDraft()
    draft.set(("dataset",), {"source": {"type": "inline", "goals": ["a", "b", "c"]}})

    plan = draft.plan()

    assert (plan.goals, plan.attacks, plan.searches) == (3, 1, 3)
