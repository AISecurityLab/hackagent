from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.evaluation_status_enum import EvaluationStatusEnum
from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchedResultRequest")


@_attrs_define
class PatchedResultRequest:
    """Serializer for the Result model, often nested in RunSerializer.

    Attributes:
        run (Union[Unset, UUID]):
        prompt (Union[None, UUID, Unset]):
        request_payload (Union[Unset, Any]): Payload sent to agent or relevant data for client-submitted results.
        response_status_code (Union[None, Unset, int]):
        response_headers (Union[Unset, Any]):
        response_body (Union[None, Unset, str]):
        latency_ms (Union[None, Unset, int]):
        detected_tool_calls (Union[Unset, Any]):
        evaluation_status (Union[Unset, EvaluationStatusEnum]): * `NOT_EVALUATED` - Not Evaluated
            * `SUCCESSFUL_JAILBREAK` - Successful Jailbreak
            * `FAILED_JAILBREAK` - Failed Jailbreak (Mitigated/Refused)
            * `ERROR_AGENT_RESPONSE` - Error in Agent Response
            * `ERROR_TEST_FRAMEWORK` - Error in Test Framework
            * `PASSED_CRITERIA` - Passed Criteria (Not Jailbreak)
            * `FAILED_CRITERIA` - Failed Criteria (Not Jailbreak)
        evaluation_notes (Union[Unset, str]):
        evaluation_metrics (Union[Unset, Any]):
        agent_specific_data (Union[Unset, Any]):
    """

    run: Union[Unset, UUID] = UNSET
    prompt: Union[None, UUID, Unset] = UNSET
    request_payload: Union[Unset, Any] = UNSET
    response_status_code: Union[None, Unset, int] = UNSET
    response_headers: Union[Unset, Any] = UNSET
    response_body: Union[None, Unset, str] = UNSET
    latency_ms: Union[None, Unset, int] = UNSET
    detected_tool_calls: Union[Unset, Any] = UNSET
    evaluation_status: Union[Unset, EvaluationStatusEnum] = UNSET
    evaluation_notes: Union[Unset, str] = UNSET
    evaluation_metrics: Union[Unset, Any] = UNSET
    agent_specific_data: Union[Unset, Any] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        run: Union[Unset, str] = UNSET
        if not isinstance(self.run, Unset):
            run = str(self.run)

        prompt: Union[None, Unset, str]
        if isinstance(self.prompt, Unset):
            prompt = UNSET
        elif isinstance(self.prompt, UUID):
            prompt = str(self.prompt)
        else:
            prompt = self.prompt

        request_payload = self.request_payload

        response_status_code: Union[None, Unset, int]
        if isinstance(self.response_status_code, Unset):
            response_status_code = UNSET
        else:
            response_status_code = self.response_status_code

        response_headers = self.response_headers

        response_body: Union[None, Unset, str]
        if isinstance(self.response_body, Unset):
            response_body = UNSET
        else:
            response_body = self.response_body

        latency_ms: Union[None, Unset, int]
        if isinstance(self.latency_ms, Unset):
            latency_ms = UNSET
        else:
            latency_ms = self.latency_ms

        detected_tool_calls = self.detected_tool_calls

        evaluation_status: Union[Unset, str] = UNSET
        if not isinstance(self.evaluation_status, Unset):
            evaluation_status = self.evaluation_status.value

        evaluation_notes = self.evaluation_notes

        evaluation_metrics = self.evaluation_metrics

        agent_specific_data = self.agent_specific_data

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if run is not UNSET:
            field_dict["run"] = run
        if prompt is not UNSET:
            field_dict["prompt"] = prompt
        if request_payload is not UNSET:
            field_dict["request_payload"] = request_payload
        if response_status_code is not UNSET:
            field_dict["response_status_code"] = response_status_code
        if response_headers is not UNSET:
            field_dict["response_headers"] = response_headers
        if response_body is not UNSET:
            field_dict["response_body"] = response_body
        if latency_ms is not UNSET:
            field_dict["latency_ms"] = latency_ms
        if detected_tool_calls is not UNSET:
            field_dict["detected_tool_calls"] = detected_tool_calls
        if evaluation_status is not UNSET:
            field_dict["evaluation_status"] = evaluation_status
        if evaluation_notes is not UNSET:
            field_dict["evaluation_notes"] = evaluation_notes
        if evaluation_metrics is not UNSET:
            field_dict["evaluation_metrics"] = evaluation_metrics
        if agent_specific_data is not UNSET:
            field_dict["agent_specific_data"] = agent_specific_data

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _run = d.pop("run", UNSET)
        run: Union[Unset, UUID]
        if isinstance(_run, Unset):
            run = UNSET
        else:
            run = UUID(_run)

        def _parse_prompt(data: object) -> Union[None, UUID, Unset]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                prompt_type_0 = UUID(data)

                return prompt_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, UUID, Unset], data)

        prompt = _parse_prompt(d.pop("prompt", UNSET))

        request_payload = d.pop("request_payload", UNSET)

        def _parse_response_status_code(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        response_status_code = _parse_response_status_code(
            d.pop("response_status_code", UNSET)
        )

        response_headers = d.pop("response_headers", UNSET)

        def _parse_response_body(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        response_body = _parse_response_body(d.pop("response_body", UNSET))

        def _parse_latency_ms(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        latency_ms = _parse_latency_ms(d.pop("latency_ms", UNSET))

        detected_tool_calls = d.pop("detected_tool_calls", UNSET)

        _evaluation_status = d.pop("evaluation_status", UNSET)
        evaluation_status: Union[Unset, EvaluationStatusEnum]
        if isinstance(_evaluation_status, Unset):
            evaluation_status = UNSET
        else:
            evaluation_status = EvaluationStatusEnum(_evaluation_status)

        evaluation_notes = d.pop("evaluation_notes", UNSET)

        evaluation_metrics = d.pop("evaluation_metrics", UNSET)

        agent_specific_data = d.pop("agent_specific_data", UNSET)

        patched_result_request = cls(
            run=run,
            prompt=prompt,
            request_payload=request_payload,
            response_status_code=response_status_code,
            response_headers=response_headers,
            response_body=response_body,
            latency_ms=latency_ms,
            detected_tool_calls=detected_tool_calls,
            evaluation_status=evaluation_status,
            evaluation_notes=evaluation_notes,
            evaluation_metrics=evaluation_metrics,
            agent_specific_data=agent_specific_data,
        )

        patched_result_request.additional_properties = d
        return patched_result_request

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
