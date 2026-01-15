from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="UserProfile")


@_attrs_define
class UserProfile:
    """
    Attributes:
        id (UUID):
        user (int):
        username (str):
        organization (UUID):
        organization_name (str):
        auth0_user_id (Union[None, str]): The unique user identifier (sub claim) provided by Auth0.
        email (Union[Unset, str]):
        first_name (Union[Unset, str]):
        last_name (Union[Unset, str]):
    """

    id: UUID
    user: int
    username: str
    organization: UUID
    organization_name: str
    auth0_user_id: Union[None, str]
    email: Union[Unset, str] = UNSET
    first_name: Union[Unset, str] = UNSET
    last_name: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        user = self.user

        username = self.username

        organization = str(self.organization)

        organization_name = self.organization_name

        auth0_user_id: Union[None, str]
        auth0_user_id = self.auth0_user_id

        email = self.email

        first_name = self.first_name

        last_name = self.last_name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "user": user,
                "username": username,
                "organization": organization,
                "organization_name": organization_name,
                "auth0_user_id": auth0_user_id,
            }
        )
        if email is not UNSET:
            field_dict["email"] = email
        if first_name is not UNSET:
            field_dict["first_name"] = first_name
        if last_name is not UNSET:
            field_dict["last_name"] = last_name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        user = d.pop("user")

        username = d.pop("username")

        organization = UUID(d.pop("organization"))

        organization_name = d.pop("organization_name")

        def _parse_auth0_user_id(data: object) -> Union[None, str]:
            if data is None:
                return data
            return cast(Union[None, str], data)

        auth0_user_id = _parse_auth0_user_id(d.pop("auth0_user_id"))

        email = d.pop("email", UNSET)

        first_name = d.pop("first_name", UNSET)

        last_name = d.pop("last_name", UNSET)

        user_profile = cls(
            id=id,
            user=user,
            username=username,
            organization=organization,
            organization_name=organization_name,
            auth0_user_id=auth0_user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )

        user_profile.additional_properties = d
        return user_profile

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
