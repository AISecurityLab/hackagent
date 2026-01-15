from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.choice_message import ChoiceMessage


T = TypeVar("T", bound="Choice")


@_attrs_define
class Choice:
    """
    Attributes:
        index (int): Index of the choice
        message (ChoiceMessage):
        finish_reason (str): Reason for completion (stop, length, etc.)
    """

    index: int
    message: "ChoiceMessage"
    finish_reason: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        index = self.index

        message = self.message.to_dict()

        finish_reason = self.finish_reason

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "index": index,
                "message": message,
                "finish_reason": finish_reason,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.choice_message import ChoiceMessage

        d = dict(src_dict)
        index = d.pop("index")

        message = ChoiceMessage.from_dict(d.pop("message"))

        finish_reason = d.pop("finish_reason")

        choice = cls(
            index=index,
            message=message,
            finish_reason=finish_reason,
        )

        choice.additional_properties = d
        return choice

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
