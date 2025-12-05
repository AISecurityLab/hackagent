import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..models.status_enum import StatusEnum
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.result import Result


T = TypeVar("T", bound="Run")


@_attrs_define
class Run:
    """Serializer for the Run model, used for both input and output.

    Attributes:
        id (UUID):
        agent (UUID):
        agent_name (str):
        owner (Union[None, int]):
        owner_username (Union[None, str]):
        organization (UUID):
        organization_name (str):
        timestamp (datetime.datetime):
        is_client_executed (bool): Indicates if the run was initiated via an Attack by a client application.
        results (list['Result']):
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

    id: UUID
    agent: UUID
    agent_name: str
    owner: Union[None, int]
    owner_username: Union[None, str]
    organization: UUID
    organization_name: str
    timestamp: datetime.datetime
    is_client_executed: bool
    results: list["Result"]
    attack: Union[None, UUID, Unset] = UNSET
    run_config: Union[Unset, Any] = UNSET
    status: Union[Unset, StatusEnum] = UNSET
    run_notes: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        agent = str(self.agent)

        agent_name = self.agent_name

        owner: Union[None, int]
        owner = self.owner

        owner_username: Union[None, str]
        owner_username = self.owner_username

        organization = str(self.organization)

        organization_name = self.organization_name

        timestamp = self.timestamp.isoformat()

        is_client_executed = self.is_client_executed

        results = []
        for results_item_data in self.results:
            results_item = results_item_data.to_dict()
            results.append(results_item)

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
                "id": id,
                "agent": agent,
                "agent_name": agent_name,
                "owner": owner,
                "owner_username": owner_username,
                "organization": organization,
                "organization_name": organization_name,
                "timestamp": timestamp,
                "is_client_executed": is_client_executed,
                "results": results,
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
        from ..models.result import Result

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        agent = UUID(d.pop("agent"))

        agent_name = d.pop("agent_name")

        def _parse_owner(data: object) -> Union[None, int]:
            if data is None:
                return data
            return cast(Union[None, int], data)

        owner = _parse_owner(d.pop("owner"))

        def _parse_owner_username(data: object) -> Union[None, str]:
            if data is None:
                return data
            return cast(Union[None, str], data)

        owner_username = _parse_owner_username(d.pop("owner_username"))

        organization = UUID(d.pop("organization"))

        organization_name = d.pop("organization_name")

        timestamp = isoparse(d.pop("timestamp"))

        is_client_executed = d.pop("is_client_executed")

        results = []
        _results = d.pop("results")
        for results_item_data in _results:
            results_item = Result.from_dict(results_item_data)

            results.append(results_item)

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

        run = cls(
            id=id,
            agent=agent,
            agent_name=agent_name,
            owner=owner,
            owner_username=owner_username,
            organization=organization,
            organization_name=organization_name,
            timestamp=timestamp,
            is_client_executed=is_client_executed,
            results=results,
            attack=attack,
            run_config=run_config,
            status=status,
            run_notes=run_notes,
        )

        run.additional_properties = d
        return run

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
