from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types

T = TypeVar("T", bound="CheckoutSessionRequestRequest")


@_attrs_define
class CheckoutSessionRequestRequest:
    """
    Attributes:
        credits_to_purchase (int): Number of credits the user wants to purchase.
    """

    credits_to_purchase: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        credits_to_purchase = self.credits_to_purchase

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "credits_to_purchase": credits_to_purchase,
            }
        )

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(
            (
                "credits_to_purchase",
                (None, str(self.credits_to_purchase).encode(), "text/plain"),
            )
        )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        credits_to_purchase = d.pop("credits_to_purchase")

        checkout_session_request_request = cls(
            credits_to_purchase=credits_to_purchase,
        )

        checkout_session_request_request.additional_properties = d
        return checkout_session_request_request

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
