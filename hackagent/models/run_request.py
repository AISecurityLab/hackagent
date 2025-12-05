from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.status_enum import StatusEnum
from ..types import UNSET, Unset

T = TypeVar("T", bound="RunRequest")


@_attrs_define
class RunRequest:
    """Serializer for the Run model, used for both input and output.

    Attributes:
        agent (UUID):
        attack (Union[None, UUID, Unset]): The Attack this run is an instance of, if applicable.
        run_config (Union[Unset, Any]): JSON containing specific settings for this run. If linked to an Attack, this
            might be a copy or subset of its configuration.
        status (Union[Unset, StatusEnum]): * `PENDING` - Pending
            * `RUNNING` - Running
            * `COMPLETED` - Completed
            * `FAILED` - Failed
            * `CANCELLED` - Cancelled
        run_notes (Union[Unset, str]):
    """

    agent: UUID
    attack: Union[None, UUID, Unset] = UNSET
    run_config: Union[Unset, Any] = UNSET
    status: Union[Unset, StatusEnum] = UNSET
    run_notes: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        agent = str(self.agent)

        attack: Union[None, Unset, str]
        if isinstance(self.attack, Unset):
            attack = UNSET
        elif isinstance(self.attack, UUID):
            attack = str(self.attack)
        else:
            attack = self.attack

        run_config = self.run_config

        status: Union[Unset, str] = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        run_notes = self.run_notes

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "agent": agent,
            }
        )
        if attack is not UNSET:
            field_dict["attack"] = attack
        if run_config is not UNSET:
            field_dict["run_config"] = run_config
        if status is not UNSET:
            field_dict["status"] = status
        if run_notes is not UNSET:
            field_dict["run_notes"] = run_notes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        agent = UUID(d.pop("agent"))

        def _parse_attack(data: object) -> Union[None, UUID, Unset]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                attack_type_0 = UUID(data)

                return attack_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, UUID, Unset], data)

        attack = _parse_attack(d.pop("attack", UNSET))

        run_config = d.pop("run_config", UNSET)

        _status = d.pop("status", UNSET)
        status: Union[Unset, StatusEnum]
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = StatusEnum(_status)

        run_notes = d.pop("run_notes", UNSET)

        run_request = cls(
            agent=agent,
            attack=attack,
            run_config=run_config,
            status=status,
            run_notes=run_notes,
        )

        run_request.additional_properties = d
        return run_request

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
