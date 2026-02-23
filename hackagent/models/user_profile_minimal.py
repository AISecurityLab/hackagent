# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID
from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="UserProfileMinimal")


@_attrs_define
class UserProfileMinimal:
    """
    Attributes:
        user (int):
        username (str):
        organization (UUID):
    """

    user: int
    username: str
    organization: UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        user = self.user

        username = self.username

        organization = str(self.organization)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "user": user,
                "username": username,
                "organization": organization,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        user = d.pop("user")

        username = d.pop("username")

        organization = UUID(d.pop("organization"))

        user_profile_minimal = cls(
            user=user,
            username=username,
            organization=organization,
        )

        user_profile_minimal.additional_properties = d
        return user_profile_minimal

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
