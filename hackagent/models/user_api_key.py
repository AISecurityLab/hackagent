import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

if TYPE_CHECKING:
    from ..models.organization_minimal import OrganizationMinimal
    from ..models.user_profile_minimal import UserProfileMinimal


T = TypeVar("T", bound="UserAPIKey")


@_attrs_define
class UserAPIKey:
    """Serializer for User API Keys.
    Exposes read-only information about the key, including its prefix.
    The full key is only shown once upon creation by the ViewSet.

        Attributes:
            id (str):
            name (str): A human-readable name for the API key.
            prefix (str):
            created (datetime.datetime):
            revoked (bool): If the API key is revoked, clients cannot use it anymore. (This cannot be undone.)
            expiry_date (Union[None, datetime.datetime]): Once API key expires, clients cannot use it anymore.
            user (int):
            user_detail (Union['UserProfileMinimal', None]):
            organization (UUID):
            organization_detail (Union['OrganizationMinimal', None]):
    """

    id: str
    name: str
    prefix: str
    created: datetime.datetime
    revoked: bool
    expiry_date: Union[None, datetime.datetime]
    user: int
    user_detail: Union["UserProfileMinimal", None]
    organization: UUID
    organization_detail: Union["OrganizationMinimal", None]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.organization_minimal import OrganizationMinimal
        from ..models.user_profile_minimal import UserProfileMinimal

        id = self.id

        name = self.name

        prefix = self.prefix

        created = self.created.isoformat()

        revoked = self.revoked

        expiry_date: Union[None, str]
        if isinstance(self.expiry_date, datetime.datetime):
            expiry_date = self.expiry_date.isoformat()
        else:
            expiry_date = self.expiry_date

        user = self.user

        user_detail: Union[None, dict[str, Any]]
        if isinstance(self.user_detail, UserProfileMinimal):
            user_detail = self.user_detail.to_dict()
        else:
            user_detail = self.user_detail

        organization = str(self.organization)

        organization_detail: Union[None, dict[str, Any]]
        if isinstance(self.organization_detail, OrganizationMinimal):
            organization_detail = self.organization_detail.to_dict()
        else:
            organization_detail = self.organization_detail

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "prefix": prefix,
                "created": created,
                "revoked": revoked,
                "expiry_date": expiry_date,
                "user": user,
                "user_detail": user_detail,
                "organization": organization,
                "organization_detail": organization_detail,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.organization_minimal import OrganizationMinimal
        from ..models.user_profile_minimal import UserProfileMinimal

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        prefix = d.pop("prefix")

        created = isoparse(d.pop("created"))

        revoked = d.pop("revoked")

        def _parse_expiry_date(data: object) -> Union[None, datetime.datetime]:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                expiry_date_type_0 = isoparse(data)

                return expiry_date_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, datetime.datetime], data)

        expiry_date = _parse_expiry_date(d.pop("expiry_date"))

        user = d.pop("user")

        def _parse_user_detail(data: object) -> Union["UserProfileMinimal", None]:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                user_detail_type_1 = UserProfileMinimal.from_dict(data)

                return user_detail_type_1
            except:  # noqa: E722
                pass
            return cast(Union["UserProfileMinimal", None], data)

        user_detail = _parse_user_detail(d.pop("user_detail"))

        organization = UUID(d.pop("organization"))

        def _parse_organization_detail(
            data: object,
        ) -> Union["OrganizationMinimal", None]:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                organization_detail_type_1 = OrganizationMinimal.from_dict(data)

                return organization_detail_type_1
            except:  # noqa: E722
                pass
            return cast(Union["OrganizationMinimal", None], data)

        organization_detail = _parse_organization_detail(d.pop("organization_detail"))

        user_api_key = cls(
            id=id,
            name=name,
            prefix=prefix,
            created=created,
            revoked=revoked,
            expiry_date=expiry_date,
            user=user,
            user_detail=user_detail,
            organization=organization,
            organization_detail=organization_detail,
        )

        user_api_key.additional_properties = d
        return user_api_key

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
