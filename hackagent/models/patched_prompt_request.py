from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchedPromptRequest")


@_attrs_define
class PatchedPromptRequest:
    """Serializer for the Prompt model.

    Attributes:
        name (Union[Unset, str]):
        prompt_text (Union[Unset, str]):
        category (Union[Unset, str]): Primary category for grouping prompts (e.g., Evasion, Harmful Content).
        tags (Union[Unset, Any]): Optional JSON list of tags for classification (e.g., ["PII", "Malware"])
        evaluation_criteria (Union[Unset, str]): Description of how success/failure should be judged for this specific
            prompt.
        expected_tool_calls (Union[Unset, Any]): JSON list of expected tool calls, e.g., [{"tool_name": "...",
            "tool_input": {...}}]
        expected_output_pattern (Union[Unset, str]): Optional regex pattern to match against the final response.
        reference_output (Union[Unset, str]): Optional ideal/reference final output text.
    """

    name: Union[Unset, str] = UNSET
    prompt_text: Union[Unset, str] = UNSET
    category: Union[Unset, str] = UNSET
    tags: Union[Unset, Any] = UNSET
    evaluation_criteria: Union[Unset, str] = UNSET
    expected_tool_calls: Union[Unset, Any] = UNSET
    expected_output_pattern: Union[Unset, str] = UNSET
    reference_output: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        prompt_text = self.prompt_text

        category = self.category

        tags = self.tags

        evaluation_criteria = self.evaluation_criteria

        expected_tool_calls = self.expected_tool_calls

        expected_output_pattern = self.expected_output_pattern

        reference_output = self.reference_output

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if prompt_text is not UNSET:
            field_dict["prompt_text"] = prompt_text
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
        d = dict(src_dict)
        name = d.pop("name", UNSET)

        prompt_text = d.pop("prompt_text", UNSET)

        category = d.pop("category", UNSET)

        tags = d.pop("tags", UNSET)

        evaluation_criteria = d.pop("evaluation_criteria", UNSET)

        expected_tool_calls = d.pop("expected_tool_calls", UNSET)

        expected_output_pattern = d.pop("expected_output_pattern", UNSET)

        reference_output = d.pop("reference_output", UNSET)

        patched_prompt_request = cls(
            name=name,
            prompt_text=prompt_text,
            category=category,
            tags=tags,
            evaluation_criteria=evaluation_criteria,
            expected_tool_calls=expected_tool_calls,
            expected_output_pattern=expected_output_pattern,
            reference_output=reference_output,
        )

        patched_prompt_request.additional_properties = d
        return patched_prompt_request

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
