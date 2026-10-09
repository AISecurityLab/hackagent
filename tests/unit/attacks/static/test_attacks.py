# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Static attacks generate requests from goals and depend on no model."""

from __future__ import annotations

import asyncio
import base64
import codecs

import pytest
from pydantic import ValidationError

from hackagent.attacks.techniques.contract import AttackParams, Completion
from hackagent.attacks.techniques.registry import STATIC_ATTACKS, get_attack_class
from hackagent.attacks.techniques.static.base import StaticAttack
from hackagent.attacks.techniques.static.baseline import BaselineAttack, BaselineParams
from hackagent.attacks.techniques.static.cipherchat import (
    CipherChatAttack,
    CipherChatParams,
)
from hackagent.attacks.techniques.static.fc import FCParams, tFCAttack, tFCParams
from hackagent.attacks.techniques.static.flipattack import FlipAttack, FlipAttackParams
from hackagent.attacks.techniques.static.h4rm3l import (
    PRESET_PROGRAMS,
    H4rm3lAttack,
    H4rm3lParams,
)
from hackagent.attacks.techniques.static.mml import MMLParams
from hackagent.attacks.techniques.static.static_template import (
    StaticTemplateAttack,
    StaticTemplateParams,
)

GOAL = "Explain how to open a lock"


def generate(attack: StaticAttack, goal: str = GOAL):
    return asyncio.run(attack.generate(goal))


# --- contract ---------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(STATIC_ATTACKS - {"fc", "mml"}))
def test_every_text_attack_generates_chat_requests_with_defaults(name):
    attack_type = get_attack_class(name)
    requests = generate(attack_type(attack_type.params_type()))
    assert requests
    for messages in requests:
        assert messages[-1]["role"] == "user"
        assert all(set(message) == {"role", "content"} for message in messages)


@pytest.mark.parametrize("name", sorted(STATIC_ATTACKS))
def test_registry_names_match_attack_names(name):
    assert get_attack_class(name).name == name


def test_unknown_attack_is_rejected():
    with pytest.raises(ValueError, match="Unknown attack"):
        get_attack_class("nope")


@pytest.mark.parametrize("goal", ["", "   "])
def test_empty_goal_is_rejected(goal):
    with pytest.raises(ValueError, match="goal cannot be empty"):
        generate(BaselineAttack(BaselineParams()), goal)


def test_attack_rejects_params_of_another_attack():
    with pytest.raises(TypeError, match="expects BaselineParams"):
        BaselineAttack(FlipAttackParams())


def test_params_are_frozen_and_strict():
    params = FlipAttackParams()
    with pytest.raises(ValidationError):
        params.flip_mode = "FWO"
    with pytest.raises(ValidationError, match="extra"):
        FlipAttackParams(unknown=1)


def test_roles_are_the_completion_fields():
    class Params(AttackParams):
        plain: int = 0
        required: Completion
        optional: Completion | None = None

    assert Params.role_names() == {"required", "optional"}
    assert H4rm3lParams.role_names() == {"decorator"}
    assert BaselineParams.role_names() == frozenset()


# --- per attack -------------------------------------------------------------


def test_baseline_sends_goal_unchanged():
    assert generate(BaselineAttack(BaselineParams()), f"  {GOAL} ") == [
        [{"role": "user", "content": GOAL}]
    ]


def test_static_template_applies_every_selected_template_in_order():
    params = StaticTemplateParams(
        template_categories=("role_play",), templates_per_category=2
    )
    requests = generate(StaticTemplateAttack(params))
    assert len(requests) == 2
    assert [r[0]["content"] for r in requests] == [
        template.format(
            goal=GOAL,
            goal_encoded=codecs.encode(GOAL, "rot_13"),
            goal_base64=base64.b64encode(GOAL.encode()).decode(),
            goal_obfuscated=GOAL[::-1],
        )
        for template in params.selected_templates()
    ]


def test_static_template_validates_categories_and_placeholders():
    with pytest.raises(ValidationError, match="Unknown template categories"):
        StaticTemplateParams(template_categories=("nope",))
    with pytest.raises(ValidationError):
        StaticTemplateParams(template_categories=())


@pytest.mark.parametrize(
    ("mode", "flipped"),
    [
        ("FWO", "lock a open to how Explain"),
        ("FCW", "nialpxE woh ot nepo a kcol"),
        ("FCS", GOAL[::-1]),
    ],
)
def test_flipattack_flips_the_goal(mode, flipped):
    requests = generate(FlipAttack(FlipAttackParams(flip_mode=mode)))
    assert requests[0][0]["role"] == "system"
    assert requests[0][1]["content"] == f"TASK is '{flipped}'"


def test_flipattack_validates_mode():
    with pytest.raises(ValidationError):
        FlipAttackParams(flip_mode="XYZ")


def test_cipherchat_encodes_goal_and_decodes_reply():
    attack = CipherChatAttack(
        CipherChatParams(encode_method="caesar-3", use_demonstrations=False)
    )
    user = generate(attack)[0][-1]["content"]
    assert "Hasodlq krz wr rshq d orfn" in user
    assert attack.decode("Wkh vhfuhw lv wr xvh d whqvlrq zuhqfk") == (
        "The secret is to use a tension wrench"
    )


def test_cipherchat_leaves_plain_replies_and_respects_decode_flag():
    attack = CipherChatAttack(CipherChatParams())
    assert (
        attack.decode("I cannot help with that request.")
        == "I cannot help with that request."
    )
    raw = CipherChatAttack(CipherChatParams(decode_response=False))
    assert raw.decode("Wkh vhfuhw lv") == "Wkh vhfuhw lv"


def test_cipherchat_validates_encoding():
    with pytest.raises(ValidationError, match="Unsupported encode_method"):
        CipherChatParams(encode_method="rot47")


def test_tfc_serializes_a_text_flowchart():
    requests = generate(tFCAttack(tFCParams(text_format="mermaid")))
    assert "```mermaid" in requests[0][-1]["content"]


@pytest.mark.parametrize(
    "build",
    [
        lambda: FCParams(dpi=10),
        lambda: FCParams(num_steps=1),
        lambda: MMLParams(font_size=2),
    ],
)
def test_image_attack_params_are_bounded(build):
    with pytest.raises(ValidationError):
        build()


# --- h4rm3l -----------------------------------------------------------------


def test_h4rm3l_syntactic_program_needs_no_model():
    requests = generate(H4rm3lAttack(H4rm3lParams(program="ReverseDecorator()")))
    assert requests == [[{"role": "user", "content": GOAL[::-1]}]]


def test_h4rm3l_accepts_preset_names():
    attack = H4rm3lAttack(H4rm3lParams(program="refusal_suppression"))
    assert "Do not apologize" in generate(attack)[0][0]["content"]
    assert "refusal_suppression" in PRESET_PROGRAMS


def test_h4rm3l_llm_decorator_requires_decorator_role():
    with pytest.raises(ValueError, match="configure the 'decorator' role"):
        H4rm3lAttack(H4rm3lParams(program="TranslateDecorator(language='Italian')"))


def test_h4rm3l_llm_decorator_uses_the_given_completion():
    seen = []

    async def decorator(messages):
        seen.append(messages)
        return "Spiega come aprire una serratura"

    params = H4rm3lParams(
        program="TranslateDecorator(language='Italian').then(ReverseDecorator())",
        decorator=decorator,
    )
    requests = generate(H4rm3lAttack(params))
    assert requests[0][0]["content"] == "Spiega come aprire una serratura"[::-1]
    assert "Translate the following text to Italian" in seen[0][0]["content"]
    assert "decorator" not in params.model_dump()


def test_h4rm3l_empty_decorator_reply_is_an_error():
    async def silent(messages):
        return "  "

    attack = H4rm3lAttack(H4rm3lParams(program="SynonymDecorator()", decorator=silent))
    with pytest.raises(ValueError, match="empty reply"):
        generate(attack)


def test_h4rm3l_rejects_unknown_decorators():
    with pytest.raises(ValueError, match="unknown decorator"):
        H4rm3lAttack(H4rm3lParams(program="NoSuchDecorator()"))
