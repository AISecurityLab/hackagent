import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

T = TypeVar("T", bound="Attack")


@_attrs_define
class Attack:
    """Serializer for the Attack model, which represents an Attack configuration.

    Handles the conversion of Attack configuration instances to JSON (and vice-versa)
    for API requests and responses. It includes read-only fields for related
    object names (like agent_name, owner_username) for convenience in API outputs.

        Attributes:
            id (UUID):
            type_ (str): A string identifier for the type of attack being configured (e.g., 'PREFIX_GENERATION',
                'PROMPT_INJECTION').
            agent (UUID):
            agent_name (str):
            owner (Union[None, int]):
            owner_username (str):
            organization (UUID):
            organization_name (str):
            configuration (Any): JSON containing client-provided configuration for an attack using this definition.
            created_at (datetime.datetime):
            updated_at (datetime.datetime):
    """

    id: UUID
    type_: str
    agent: UUID
    agent_name: str
    owner: Union[None, int]
    owner_username: str
    organization: UUID
    organization_name: str
    configuration: Any
    created_at: datetime.datetime
    updated_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        type_ = self.type_

        agent = str(self.agent)

        agent_name = self.agent_name

        owner: Union[None, int]
        owner = self.owner

        owner_username = self.owner_username

        organization = str(self.organization)

        organization_name = self.organization_name

        configuration = self.configuration

        created_at = self.created_at.isoformat()

        updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "type": type_,
                "agent": agent,
                "agent_name": agent_name,
                "owner": owner,
                "owner_username": owner_username,
                "organization": organization,
                "organization_name": organization_name,
                "configuration": configuration,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        type_ = d.pop("type")

        agent = UUID(d.pop("agent"))

        agent_name = d.pop("agent_name")

        def _parse_owner(data: object) -> Union[None, int]:
            if data is None:
                return data
            return cast(Union[None, int], data)

        owner = _parse_owner(d.pop("owner"))

        owner_username = d.pop("owner_username")

        organization = UUID(d.pop("organization"))

        organization_name = d.pop("organization_name")

        configuration = d.pop("configuration")

        created_at = isoparse(d.pop("created_at"))

        updated_at = isoparse(d.pop("updated_at"))

        attack = cls(
            id=id,
            type_=type_,
            agent=agent,
            agent_name=agent_name,
            owner=owner,
            owner_username=owner_username,
            organization=organization,
            organization_name=organization_name,
            configuration=configuration,
            created_at=created_at,
            updated_at=updated_at,
        )

        attack.additional_properties = d
        return attack

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
