import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

T = TypeVar("T", bound="APITokenLog")


@_attrs_define
class APITokenLog:
    """Serializer for APITokenLog model, providing read-only access to log entries.

    Attributes:
        id (int):
        timestamp (datetime.datetime):
        api_key_prefix (Union[None, str]):
        user_username (Union[None, str]):
        organization_name (Union[None, str]):
        model_id_used (str): Identifier of the AI model used.
        api_endpoint (str): Internal endpoint name, e.g., 'generator' or 'judge'.
        input_tokens (int):
        output_tokens (int):
        credits_deducted (str):
        request_payload_preview (Union[None, str]): First ~256 chars of request payload
        response_payload_preview (Union[None, str]): First ~256 chars of response payload
    """

    id: int
    timestamp: datetime.datetime
    api_key_prefix: Union[None, str]
    user_username: Union[None, str]
    organization_name: Union[None, str]
    model_id_used: str
    api_endpoint: str
    input_tokens: int
    output_tokens: int
    credits_deducted: str
    request_payload_preview: Union[None, str]
    response_payload_preview: Union[None, str]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        timestamp = self.timestamp.isoformat()

        api_key_prefix: Union[None, str]
        api_key_prefix = self.api_key_prefix

        user_username: Union[None, str]
        user_username = self.user_username

        organization_name: Union[None, str]
        organization_name = self.organization_name

        model_id_used = self.model_id_used

        api_endpoint = self.api_endpoint

        input_tokens = self.input_tokens

        output_tokens = self.output_tokens

        credits_deducted = self.credits_deducted

        request_payload_preview: Union[None, str]
        request_payload_preview = self.request_payload_preview

        response_payload_preview: Union[None, str]
        response_payload_preview = self.response_payload_preview

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "timestamp": timestamp,
                "api_key_prefix": api_key_prefix,
                "user_username": user_username,
                "organization_name": organization_name,
                "model_id_used": model_id_used,
                "api_endpoint": api_endpoint,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "credits_deducted": credits_deducted,
                "request_payload_preview": request_payload_preview,
                "response_payload_preview": response_payload_preview,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        timestamp = isoparse(d.pop("timestamp"))

        def _parse_api_key_prefix(data: object) -> Union[None, str]:
            if data is None:
                return data
            return cast(Union[None, str], data)

        api_key_prefix = _parse_api_key_prefix(d.pop("api_key_prefix"))

        def _parse_user_username(data: object) -> Union[None, str]:
            if data is None:
                return data
            return cast(Union[None, str], data)

        user_username = _parse_user_username(d.pop("user_username"))

        def _parse_organization_name(data: object) -> Union[None, str]:
            if data is None:
                return data
            return cast(Union[None, str], data)

        organization_name = _parse_organization_name(d.pop("organization_name"))

        model_id_used = d.pop("model_id_used")

        api_endpoint = d.pop("api_endpoint")

        input_tokens = d.pop("input_tokens")

        output_tokens = d.pop("output_tokens")

        credits_deducted = d.pop("credits_deducted")

        def _parse_request_payload_preview(data: object) -> Union[None, str]:
            if data is None:
                return data
            return cast(Union[None, str], data)

        request_payload_preview = _parse_request_payload_preview(
            d.pop("request_payload_preview")
        )

        def _parse_response_payload_preview(data: object) -> Union[None, str]:
            if data is None:
                return data
            return cast(Union[None, str], data)

        response_payload_preview = _parse_response_payload_preview(
            d.pop("response_payload_preview")
        )

        api_token_log = cls(
            id=id,
            timestamp=timestamp,
            api_key_prefix=api_key_prefix,
            user_username=user_username,
            organization_name=organization_name,
            model_id_used=model_id_used,
            api_endpoint=api_endpoint,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            credits_deducted=credits_deducted,
            request_payload_preview=request_payload_preview,
            response_payload_preview=response_payload_preview,
        )

        api_token_log.additional_properties = d
        return api_token_log

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
