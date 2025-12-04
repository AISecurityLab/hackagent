from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.step_type_enum import StepTypeEnum
from ..types import UNSET, Unset

T = TypeVar("T", bound="TraceRequest")


@_attrs_define
class TraceRequest:
    """Serializer for the Trace model.

    Attributes:
        sequence (int):
        step_type (Union[Unset, StepTypeEnum]): * `TOOL_CALL` - Tool Call
            * `TOOL_RESPONSE` - Tool Response
            * `AGENT_THOUGHT` - Agent Thought/Reasoning
            * `AGENT_RESPONSE_CHUNK` - Agent Response Chunk
            * `OTHER` - Other
            * `MCP_STEP` - Multi-Context Prompting Step
            * `A2A_COMM` - Agent-to-Agent Communication
        content (Union[Unset, Any]):
    """

    sequence: int
    step_type: Union[Unset, StepTypeEnum] = UNSET
    content: Union[Unset, Any] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        sequence = self.sequence

        step_type: Union[Unset, str] = UNSET
        if not isinstance(self.step_type, Unset):
            step_type = self.step_type.value

        content = self.content

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "sequence": sequence,
            }
        )
        if step_type is not UNSET:
            field_dict["step_type"] = step_type
        if content is not UNSET:
            field_dict["content"] = content

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        sequence = d.pop("sequence")

        _step_type = d.pop("step_type", UNSET)
        step_type: Union[Unset, StepTypeEnum]
        if isinstance(_step_type, Unset):
            step_type = UNSET
        else:
            step_type = StepTypeEnum(_step_type)

        content = d.pop("content", UNSET)

        trace_request = cls(
            sequence=sequence,
            step_type=step_type,
            content=content,
        )

        trace_request.additional_properties = d
        return trace_request

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
