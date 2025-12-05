import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.message_request import MessageRequest


T = TypeVar("T", bound="GenerateRequestRequest")


@_attrs_define
class GenerateRequestRequest:
    """
    Attributes:
        messages (list['MessageRequest']): Array of conversation messages
        model (Union[Unset, str]): Client-specified model (will be overridden by server)
        stream (Union[Unset, bool]): Whether to stream the response Default: False.
        temperature (Union[Unset, float]): Sampling temperature (0-2)
        max_tokens (Union[Unset, int]): Maximum tokens to generate
        top_p (Union[Unset, float]): Nucleus sampling threshold
        frequency_penalty (Union[Unset, float]): Frequency penalty (-2.0 to 2.0)
        presence_penalty (Union[Unset, float]): Presence penalty (-2.0 to 2.0)
        stop (Union[Unset, list[str]]): Sequences where the API will stop generating
    """

    messages: list["MessageRequest"]
    model: Union[Unset, str] = UNSET
    stream: Union[Unset, bool] = False
    temperature: Union[Unset, float] = UNSET
    max_tokens: Union[Unset, int] = UNSET
    top_p: Union[Unset, float] = UNSET
    frequency_penalty: Union[Unset, float] = UNSET
    presence_penalty: Union[Unset, float] = UNSET
    stop: Union[Unset, list[str]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        messages = []
        for messages_item_data in self.messages:
            messages_item = messages_item_data.to_dict()
            messages.append(messages_item)

        model = self.model

        stream = self.stream

        temperature = self.temperature

        max_tokens = self.max_tokens

        top_p = self.top_p

        frequency_penalty = self.frequency_penalty

        presence_penalty = self.presence_penalty

        stop: Union[Unset, list[str]] = UNSET
        if not isinstance(self.stop, Unset):
            stop = self.stop

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "messages": messages,
            }
        )
        if model is not UNSET:
            field_dict["model"] = model
        if stream is not UNSET:
            field_dict["stream"] = stream
        if temperature is not UNSET:
            field_dict["temperature"] = temperature
        if max_tokens is not UNSET:
            field_dict["max_tokens"] = max_tokens
        if top_p is not UNSET:
            field_dict["top_p"] = top_p
        if frequency_penalty is not UNSET:
            field_dict["frequency_penalty"] = frequency_penalty
        if presence_penalty is not UNSET:
            field_dict["presence_penalty"] = presence_penalty
        if stop is not UNSET:
            field_dict["stop"] = stop

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        for messages_item_element in self.messages:
            files.append(
                (
                    "messages",
                    (
                        None,
                        json.dumps(messages_item_element.to_dict()).encode(),
                        "application/json",
                    ),
                )
            )

        if not isinstance(self.model, Unset):
            files.append(("model", (None, str(self.model).encode(), "text/plain")))

        if not isinstance(self.stream, Unset):
            files.append(("stream", (None, str(self.stream).encode(), "text/plain")))

        if not isinstance(self.temperature, Unset):
            files.append(
                ("temperature", (None, str(self.temperature).encode(), "text/plain"))
            )

        if not isinstance(self.max_tokens, Unset):
            files.append(
                ("max_tokens", (None, str(self.max_tokens).encode(), "text/plain"))
            )

        if not isinstance(self.top_p, Unset):
            files.append(("top_p", (None, str(self.top_p).encode(), "text/plain")))

        if not isinstance(self.frequency_penalty, Unset):
            files.append(
                (
                    "frequency_penalty",
                    (None, str(self.frequency_penalty).encode(), "text/plain"),
                )
            )

        if not isinstance(self.presence_penalty, Unset):
            files.append(
                (
                    "presence_penalty",
                    (None, str(self.presence_penalty).encode(), "text/plain"),
                )
            )

        if not isinstance(self.stop, Unset):
            for stop_item_element in self.stop:
                files.append(
                    ("stop", (None, str(stop_item_element).encode(), "text/plain"))
                )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.message_request import MessageRequest

        d = dict(src_dict)
        messages = []
        _messages = d.pop("messages")
        for messages_item_data in _messages:
            messages_item = MessageRequest.from_dict(messages_item_data)

            messages.append(messages_item)

        model = d.pop("model", UNSET)

        stream = d.pop("stream", UNSET)

        temperature = d.pop("temperature", UNSET)

        max_tokens = d.pop("max_tokens", UNSET)

        top_p = d.pop("top_p", UNSET)

        frequency_penalty = d.pop("frequency_penalty", UNSET)

        presence_penalty = d.pop("presence_penalty", UNSET)

        stop = cast(list[str], d.pop("stop", UNSET))

        generate_request_request = cls(
            messages=messages,
            model=model,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            stop=stop,
        )

        generate_request_request.additional_properties = d
        return generate_request_request

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
