import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..models.step_type_enum import StepTypeEnum
from ..types import UNSET, Unset

T = TypeVar("T", bound="Trace")


@_attrs_define
class Trace:
    """Serializer for the Trace model.

    Attributes:
        id (int):
        result (UUID):
        sequence (int):
        timestamp (datetime.datetime):
        step_type (Union[Unset, StepTypeEnum]): * `TOOL_CALL` - Tool Call
            * `TOOL_RESPONSE` - Tool Response
            * `AGENT_THOUGHT` - Agent Thought/Reasoning
            * `AGENT_RESPONSE_CHUNK` - Agent Response Chunk
            * `OTHER` - Other
            * `MCP_STEP` - Multi-Context Prompting Step
            * `A2A_COMM` - Agent-to-Agent Communication
        content (Union[Unset, Any]):
    """

    id: int
    result: UUID
    sequence: int
    timestamp: datetime.datetime
    step_type: Union[Unset, StepTypeEnum] = UNSET
    content: Union[Unset, Any] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        result = str(self.result)

        sequence = self.sequence

        timestamp = self.timestamp.isoformat()

        step_type: Union[Unset, str] = UNSET
        if not isinstance(self.step_type, Unset):
            step_type = self.step_type.value

        content = self.content

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "result": result,
                "sequence": sequence,
                "timestamp": timestamp,
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
        id = d.pop("id")

        result = UUID(d.pop("result"))

        sequence = d.pop("sequence")

        timestamp = isoparse(d.pop("timestamp"))

        _step_type = d.pop("step_type", UNSET)
        step_type: Union[Unset, StepTypeEnum]
        if isinstance(_step_type, Unset):
            step_type = UNSET
        else:
            step_type = StepTypeEnum(_step_type)

        content = d.pop("content", UNSET)

        trace = cls(
            id=id,
            result=result,
            sequence=sequence,
            timestamp=timestamp,
            step_type=step_type,
            content=content,
        )

        trace.additional_properties = d
        return trace

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
