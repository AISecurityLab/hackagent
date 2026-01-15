import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.organization_minimal import OrganizationMinimal
    from ..models.user_profile_minimal import UserProfileMinimal


T = TypeVar("T", bound="Prompt")


@_attrs_define
class Prompt:
    """Serializer for the Prompt model.

    Attributes:
        id (UUID):
        name (str):
        prompt_text (str):
        organization (UUID):
        organization_detail (OrganizationMinimal):
        owner (Union[None, int]):
        owner_detail (Union['UserProfileMinimal', None]):
        created_at (datetime.datetime):
        updated_at (datetime.datetime):
        category (Union[Unset, str]): Primary category for grouping prompts (e.g., Evasion, Harmful Content).
        tags (Union[Unset, Any]): Optional JSON list of tags for classification (e.g., ["PII", "Malware"])
        evaluation_criteria (Union[Unset, str]): Description of how success/failure should be judged for this specific
            prompt.
        expected_tool_calls (Union[Unset, Any]): JSON list of expected tool calls, e.g., [{"tool_name": "...",
            "tool_input": {...}}]
        expected_output_pattern (Union[Unset, str]): Optional regex pattern to match against the final response.
        reference_output (Union[Unset, str]): Optional ideal/reference final output text.
    """

    id: UUID
    name: str
    prompt_text: str
    organization: UUID
    organization_detail: "OrganizationMinimal"
    owner: Union[None, int]
    owner_detail: Union["UserProfileMinimal", None]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    category: Union[Unset, str] = UNSET
    tags: Union[Unset, Any] = UNSET
    evaluation_criteria: Union[Unset, str] = UNSET
    expected_tool_calls: Union[Unset, Any] = UNSET
    expected_output_pattern: Union[Unset, str] = UNSET
    reference_output: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.user_profile_minimal import UserProfileMinimal

        id = str(self.id)

        name = self.name

        prompt_text = self.prompt_text

        organization = str(self.organization)

        organization_detail = self.organization_detail.to_dict()

        owner: Union[None, int]
        owner = self.owner

        owner_detail: Union[None, dict[str, Any]]
        if isinstance(self.owner_detail, UserProfileMinimal):
            owner_detail = self.owner_detail.to_dict()
        else:
            owner_detail = self.owner_detail

        created_at = self.created_at.isoformat()

        updated_at = self.updated_at.isoformat()

        category = self.category

        tags = self.tags

        evaluation_criteria = self.evaluation_criteria

        expected_tool_calls = self.expected_tool_calls

        expected_output_pattern = self.expected_output_pattern

        reference_output = self.reference_output

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "prompt_text": prompt_text,
                "organization": organization,
                "organization_detail": organization_detail,
                "owner": owner,
                "owner_detail": owner_detail,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
        if category is not UNSET:
            field_dict["category"] = category
        if tags is not UNSET:
            field_dict["tags"] = tags
        if evaluation_criteria is not UNSET:
            field_dict["evaluation_criteria"] = evaluation_criteria
        if expected_tool_calls is not UNSET:
            field_dict["expected_tool_calls"] = expected_tool_calls
        if expected_output_pattern is not UNSET:
            field_dict["expected_output_pattern"] = expected_output_pattern
        if reference_output is not UNSET:
            field_dict["reference_output"] = reference_output

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.organization_minimal import OrganizationMinimal
        from ..models.user_profile_minimal import UserProfileMinimal

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        name = d.pop("name")

        prompt_text = d.pop("prompt_text")

        organization = UUID(d.pop("organization"))

        organization_detail = OrganizationMinimal.from_dict(
            d.pop("organization_detail")
        )

        def _parse_owner(data: object) -> Union[None, int]:
            if data is None:
                return data
            return cast(Union[None, int], data)

        owner = _parse_owner(d.pop("owner"))

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

        category = d.pop("category", UNSET)

        tags = d.pop("tags", UNSET)

        evaluation_criteria = d.pop("evaluation_criteria", UNSET)

        expected_tool_calls = d.pop("expected_tool_calls", UNSET)

        expected_output_pattern = d.pop("expected_output_pattern", UNSET)

        reference_output = d.pop("reference_output", UNSET)

        prompt = cls(
            id=id,
            name=name,
            prompt_text=prompt_text,
            organization=organization,
            organization_detail=organization_detail,
            owner=owner,
            owner_detail=owner_detail,
            created_at=created_at,
            updated_at=updated_at,
            category=category,
            tags=tags,
            evaluation_criteria=evaluation_criteria,
            expected_tool_calls=expected_tool_calls,
            expected_output_pattern=expected_output_pattern,
            reference_output=reference_output,
        )

        prompt.additional_properties = d
        return prompt

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
