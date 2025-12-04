from collections.abc import Mapping
from typing import Any, TypeVar, Union
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchedAttackRequest")


@_attrs_define
class PatchedAttackRequest:
    """Serializer for the Attack model, which represents an Attack configuration.

    Handles the conversion of Attack configuration instances to JSON (and vice-versa)
    for API requests and responses. It includes read-only fields for related
    object names (like agent_name, owner_username) for convenience in API outputs.

        Attributes:
            type_ (Union[Unset, str]): A string identifier for the type of attack being configured (e.g.,
                'PREFIX_GENERATION', 'PROMPT_INJECTION').
            agent (Union[Unset, UUID]):
            configuration (Union[Unset, Any]): JSON containing client-provided configuration for an attack using this
                definition.
    """

    type_: Union[Unset, str] = UNSET
    agent: Union[Unset, UUID] = UNSET
    configuration: Union[Unset, Any] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_

        agent: Union[Unset, str] = UNSET
        if not isinstance(self.agent, Unset):
            agent = str(self.agent)

        configuration = self.configuration

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if type_ is not UNSET:
            field_dict["type"] = type_
        if agent is not UNSET:
            field_dict["agent"] = agent
        if configuration is not UNSET:
            field_dict["configuration"] = configuration

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        type_ = d.pop("type", UNSET)

        _agent = d.pop("agent", UNSET)
        agent: Union[Unset, UUID]
        if isinstance(_agent, Unset):
            agent = UNSET
        else:
            agent = UUID(_agent)

        configuration = d.pop("configuration", UNSET)

        patched_attack_request = cls(
            type_=type_,
            agent=agent,
            configuration=configuration,
        )

        patched_attack_request.additional_properties = d
        return patched_attack_request

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
