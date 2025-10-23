import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..models.agent_type_enum import AgentTypeEnum
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.organization_minimal import OrganizationMinimal
    from ..models.user_profile_minimal import UserProfileMinimal


T = TypeVar("T", bound="Agent")


@_attrs_define
class Agent:
    """Serializes Agent model instances to JSON and validates data for creating
    or updating Agent instances.

    This serializer provides a comprehensive representation of an Agent,
    including its type, endpoint, and nested details for related 'organization'
    and 'owner' for read operations, while allowing 'organization' and 'owner' IDs
    for write operations.

    Attributes:
        organization_detail (OrganizationMinimalSerializer): Read-only nested
            serializer for the agent's organization. Displays minimal details.
        owner_detail (UserProfileMinimalSerializer): Read-only nested serializer
            for the agent's owner's user profile. Displays minimal details.
            Can be null if the agent has no owner or the owner has no profile.
        type (CharField): The type of the agent (e.g., GENERIC_ADK, OPENAI_SDK).
                          Uses the choices defined in the Agent model's AgentType enum.

    Meta:
        model (Agent): The model class that this serializer works with.
        fields (tuple): The fields to include in the serialized output.
            Includes standard Agent fields like 'endpoint', 'type',
            and the read-only nested details.
        read_only_fields (tuple): Fields that are read-only and cannot be
            set during create/update operations through this serializer.
            This includes 'id', 'created_at', 'updated_at', and the
            nested detail fields.

        Attributes:
            id (UUID):
            name (str):
            endpoint (str): The primary API endpoint URL for interacting with the agent.
            organization (UUID):
            organization_detail (OrganizationMinimal):
            owner_detail (Union['UserProfileMinimal', None]):
            created_at (datetime.datetime):
            updated_at (datetime.datetime):
            agent_type (Union[Unset, AgentTypeEnum]): * `LITELLM` - LiteLLM
                * `OPENAI_SDK` - OpenAI SDK/API
                * `GOOGLE_ADK` - Google ADK
                * `OTHER` - Other/Proprietary
                * `UNKNOWN` - Unknown
            description (Union[Unset, str]):
            metadata (Union[Unset, Any]): Optional JSON data providing specific details and configuration. Structure depends
                heavily on Agent Type. Examples:
                - For GENERIC_ADK: {'adk_app_name': 'my_adk_app', 'protocol_version': '1.0'}
                - For OPENAI_SDK: {'model': 'gpt-4-turbo', 'api_key_secret_name': 'MY_OPENAI_KEY', 'instructions': 'You are a
                helpful assistant.'}
                - For GOOGLE_ADK: {'project_id': 'my-gcp-project', 'location': 'us-central1'}
                - General applicable: {'version': '1.2.0', 'custom_headers': {'X-Custom-Header': 'value'}}
            owner (Union[None, Unset, int]):
    """

    id: UUID
    name: str
    endpoint: str
    organization: UUID
    organization_detail: "OrganizationMinimal"
    owner_detail: Union["UserProfileMinimal", None]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    agent_type: Union[Unset, AgentTypeEnum] = UNSET
    description: Union[Unset, str] = UNSET
    metadata: Union[Unset, Any] = UNSET
    owner: Union[None, Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.user_profile_minimal import UserProfileMinimal

        id = str(self.id)

        name = self.name

        endpoint = self.endpoint

        organization = str(self.organization)

        organization_detail = self.organization_detail.to_dict()

        owner_detail: Union[None, dict[str, Any]]
        if isinstance(self.owner_detail, UserProfileMinimal):
            owner_detail = self.owner_detail.to_dict()
        else:
            owner_detail = self.owner_detail

        created_at = self.created_at.isoformat()

        updated_at = self.updated_at.isoformat()

        agent_type: Union[Unset, str] = UNSET
        if not isinstance(self.agent_type, Unset):
            agent_type = self.agent_type.value

        description = self.description

        metadata = self.metadata

        owner: Union[None, Unset, int]
        if isinstance(self.owner, Unset):
            owner = UNSET
        else:
            owner = self.owner

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "endpoint": endpoint,
                "organization": organization,
                "organization_detail": organization_detail,
                "owner_detail": owner_detail,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
        if agent_type is not UNSET:
            field_dict["agent_type"] = agent_type
        if description is not UNSET:
            field_dict["description"] = description
        if metadata is not UNSET:
            field_dict["metadata"] = metadata
        if owner is not UNSET:
            field_dict["owner"] = owner

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.organization_minimal import OrganizationMinimal
        from ..models.user_profile_minimal import UserProfileMinimal

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        name = d.pop("name")

        endpoint = d.pop("endpoint")

        organization = UUID(d.pop("organization"))

        organization_detail = OrganizationMinimal.from_dict(
            d.pop("organization_detail")
        )

        def _parse_owner_detail(data: object) -> Union["UserProfileMinimal", None]:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                owner_detail_type_1 = UserProfileMinimal.from_dict(data)

                return owner_detail_type_1
            except:  # noqa: E722
                pass
            return cast(Union["UserProfileMinimal", None], data)

        owner_detail = _parse_owner_detail(d.pop("owner_detail"))

        created_at = isoparse(d.pop("created_at"))

        updated_at = isoparse(d.pop("updated_at"))

        _agent_type = d.pop("agent_type", UNSET)
        agent_type: Union[Unset, AgentTypeEnum]
        if isinstance(_agent_type, Unset):
            agent_type = UNSET
        else:
            agent_type = AgentTypeEnum(_agent_type)

        description = d.pop("description", UNSET)

        metadata = d.pop("metadata", UNSET)

        def _parse_owner(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        owner = _parse_owner(d.pop("owner", UNSET))

        agent = cls(
            id=id,
            name=name,
            endpoint=endpoint,
            organization=organization,
            organization_detail=organization_detail,
            owner_detail=owner_detail,
            created_at=created_at,
            updated_at=updated_at,
            agent_type=agent_type,
            description=description,
            metadata=metadata,
            owner=owner,
        )

        agent.additional_properties = d
        return agent

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
