from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AgentRequest")


@_attrs_define
class AgentRequest:
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
        agent_type (CharField): The type of the agent as a string
                          (e.g., LITELLM, OPENAI_SDK, GOOGLE_ADK).

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
            name (str):
            endpoint (str): The primary API endpoint URL for interacting with the agent.
            agent_type (Union[Unset, str]): The specific SDK, ADK, or API type the agent is built upon (e.g., OpenAI SDK,
                Generic ADK).
            description (Union[Unset, str]):
            metadata (Union[Unset, Any]): Optional JSON data providing specific details and configuration. Structure depends
                heavily on Agent Type. Examples:
                - For GENERIC_ADK: {'adk_app_name': 'my_adk_app', 'protocol_version': '1.0'}
                - For OPENAI_SDK: {'model': 'gpt-4-turbo', 'api_key_secret_name': 'MY_OPENAI_KEY', 'instructions': 'You are a
                helpful assistant.'}
                - For GOOGLE_ADK: {'project_id': 'my-gcp-project', 'location': 'us-central1'}
                - General applicable: {'version': '1.2.0', 'custom_headers': {'X-Custom-Header': 'value'}}
    """

    name: str
    endpoint: str
    agent_type: Union[Unset, str] = UNSET
    description: Union[Unset, str] = UNSET
    metadata: Union[Unset, Any] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        endpoint = self.endpoint

        agent_type = self.agent_type

        description = self.description

        metadata = self.metadata

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "endpoint": endpoint,
            }
        )
        if agent_type is not UNSET:
            field_dict["agent_type"] = agent_type
        if description is not UNSET:
            field_dict["description"] = description
        if metadata is not UNSET:
            field_dict["metadata"] = metadata

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        endpoint = d.pop("endpoint")

        agent_type = d.pop("agent_type", UNSET)

        description = d.pop("description", UNSET)

        metadata = d.pop("metadata", UNSET)

        agent_request = cls(
            name=name,
            endpoint=endpoint,
            agent_type=agent_type,
            description=description,
            metadata=metadata,
        )

        agent_request.additional_properties = d
        return agent_request

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
