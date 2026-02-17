# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID
from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AttackRequest")


@_attrs_define
class AttackRequest:
    """Serializer for the Attack model, which represents an Attack configuration.
    Handles the conversion of Attack configuration instances to JSON (and vice-versa)
    for API requests and responses. It includes read-only fields for related
    object names (like agent_name, owner_username) for convenience in API outputs.

        Attributes:
            type_ (str): A string identifier for the type of attack being configured (e.g., 'PREFIX_GENERATION',
                'PROMPT_INJECTION').
            agent (UUID):
            configuration (Any): JSON containing client-provided configuration for an attack using this definition.
    """

    type_: str
    agent: UUID
    configuration: Any
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_

        agent = str(self.agent)

        configuration = self.configuration

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
                "agent": agent,
                "configuration": configuration,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        type_ = d.pop("type")

        agent = UUID(d.pop("agent"))

        configuration = d.pop("configuration")

        attack_request = cls(
            type_=type_,
            agent=agent,
            configuration=configuration,
        )

        attack_request.additional_properties = d
        return attack_request

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
