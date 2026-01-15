from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.choice import Choice
    from ..models.usage import Usage


T = TypeVar("T", bound="GenerateSuccessResponse")


@_attrs_define
class GenerateSuccessResponse:
    """
    Attributes:
        id (str): Unique identifier for the completion
        object_ (str): Object type (chat.completion)
        created (int): Unix timestamp of creation
        model (str): Model used for generation
        choices (list['Choice']): Array of completion choices
        usage (Usage):
    """

    id: str
    object_: str
    created: int
    model: str
    choices: list["Choice"]
    usage: "Usage"
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        object_ = self.object_

        created = self.created

        model = self.model

        choices = []
        for choices_item_data in self.choices:
            choices_item = choices_item_data.to_dict()
            choices.append(choices_item)

        usage = self.usage.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "object": object_,
                "created": created,
                "model": model,
                "choices": choices,
                "usage": usage,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.choice import Choice
        from ..models.usage import Usage

        d = dict(src_dict)
        id = d.pop("id")

        object_ = d.pop("object")

        created = d.pop("created")

        model = d.pop("model")

        choices = []
        _choices = d.pop("choices")
        for choices_item_data in _choices:
            choices_item = Choice.from_dict(choices_item_data)

            choices.append(choices_item)

        usage = Usage.from_dict(d.pop("usage"))

        generate_success_response = cls(
            id=id,
            object_=object_,
            created=created,
            model=model,
            choices=choices,
            usage=usage,
        )

        generate_success_response.additional_properties = d
        return generate_success_response

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
