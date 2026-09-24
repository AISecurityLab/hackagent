# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Facade (depth 2).

``HackAgent`` is constructed from :class:`~hackagent.core.settings.Settings`
and does not require a target. :meth:`HackAgent.target` binds an endpoint and
returns an object whose :meth:`~Target.hack` and :meth:`~Target.hack_chain`
both accept ``on_event``. Interfaces talk only to this module and the public
types re-exported from :mod:`hackagent`.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import UUID

from hackagent.core.contracts import AgentType
from hackagent.core.errors import HackAgentError
from hackagent.core.logging import get_logger
from hackagent.core.settings import Settings

logger = get_logger(__name__)

EventCallback = Callable[..., None]

_SKIP_FORM_KEYS = {"attack_type", "goals", "dataset", "intents", "output_dir"}
_CATEGORY_ORDER = ("static", "adaptive", "multi_turn")


def _open_store(
    settings: Settings,
    *,
    backend: Any,
    timeout: Optional[float],
    raise_on_unexpected_status: bool,
) -> Any:
    if backend is not None:
        logger.info("HackAgent using caller-provided backend %s", type(backend).__name__)
        return backend
    if settings.api_key:
        from hackagent.storage.remote import RemoteBackend

        logger.info("HackAgent using remote backend → %s", settings.base_url)
        return RemoteBackend.connect(
            settings.base_url,
            settings.api_key,
            timeout=timeout,
            raise_on_unexpected_status=raise_on_unexpected_status,
        )
    from hackagent.storage.local import LocalBackend

    logger.info(
        "HackAgent using local backend → %s. Set HACKAGENT_API_KEY or "
        "pass api_key= to enable remote tracking.",
        settings.db_path,
    )
    return LocalBackend(db_path=settings.db_path)


def _as_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


class _CallbackBus:
    """Adapt an ``on_event`` callback to the emitter the runner calls."""

    def __init__(self, callback: EventCallback) -> None:
        self._callback = callback

    def emit(self, event_type: str, **payload: Any) -> None:
        self._callback(event_type, **payload)


def _as_bus(on_event: Any) -> Any:
    if on_event is None:
        return None
    if hasattr(on_event, "emit"):
        return on_event
    return _CallbackBus(on_event)


def _guardrail_sides(
    guardrails: Any,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not guardrails:
        return None, None
    if isinstance(guardrails, dict):
        return guardrails.get("before"), guardrails.get("after")
    return None, None


# ---------------------------------------------------------------------------
# Catalog, presets, planning — no store required
# ---------------------------------------------------------------------------


def _primary_orders() -> Dict[str, int]:
    from hackagent.catalog.risks.jailbreak import JAILBREAK_PROFILE

    return {
        rec.technique: index
        for index, rec in enumerate(JAILBREAK_PROFILE.primary_attacks)
    }


def primary_dataset() -> Optional[str]:
    """Preset used by the default jailbreak campaign when none is chosen."""
    from hackagent.catalog.risks.jailbreak import JAILBREAK_PROFILE

    datasets = JAILBREAK_PROFILE.primary_datasets
    if not datasets:
        return None
    return datasets[0].preset


def primary_attacks() -> List[str]:
    """Jailbreak campaign technique ids, in campaign order."""
    return [
        attack_id
        for attack_id, _index in sorted(
            _primary_orders().items(), key=lambda item: item[1]
        )
    ]


def presets() -> Dict[str, Dict[str, Any]]:
    """Built-in dataset presets, keyed by name."""
    from hackagent.datasets.presets import PRESETS

    return {name: dict(config) for name, config in PRESETS.items()}


def preset(name: str) -> Dict[str, Any]:
    """Return one preset configuration.

    Raises:
        ValueError: The name is not a known preset.
    """
    from hackagent.datasets.presets import get_preset

    return get_preset(name)


def load_goals(**kwargs: Any) -> List[Any]:
    """Load goals through the datasets package."""
    from hackagent.datasets import load_goals as _load_goals

    return _load_goals(**kwargs)


def _schema_type(prop: Dict[str, Any]) -> str:
    raw = prop.get("type")
    if isinstance(raw, list):
        raw = next((item for item in raw if item != "null"), "string")
    if raw:
        return str(raw)
    for option in prop.get("anyOf") or prop.get("oneOf") or []:
        if isinstance(option, dict) and option.get("type") not in (None, "null"):
            return str(option["type"])
    return "string"


def _resolve_schema(schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        target = defs.get(ref.rsplit("/", 1)[-1], {})
        merged = dict(target)
        for key, value in schema.items():
            if key != "$ref":
                merged[key] = value
        return merged
    return schema


def _form_fields_from_schema(
    schema: Dict[str, Any], defs: Dict[str, Any], *, prefix: str
) -> List[Dict[str, Any]]:
    resolved = _resolve_schema(schema, defs)
    properties = resolved.get("properties") or {}
    required = set(resolved.get("required") or [])
    fields: List[Dict[str, Any]] = []
    for key, raw in properties.items():
        if key in _SKIP_FORM_KEYS and not prefix:
            continue
        prop = _resolve_schema(raw, defs)
        path = f"{prefix}.{key}" if prefix else key
        nested = prop.get("properties")
        type_name = _schema_type(prop)
        if nested or (type_name == "object" and "$ref" in raw):
            fields.extend(_form_fields_from_schema(prop, defs, prefix=path))
            continue
        if type_name in {"object", "array"} or "properties" in prop:
            continue
        choices = prop.get("enum")
        if choices is None and isinstance(prop.get("choices"), list):
            choices = prop["choices"]
        choice_pairs = None
        if isinstance(choices, list):
            choice_pairs = [
                list(item) if isinstance(item, (list, tuple)) else [str(item), item]
                for item in choices
            ]
        label = str(prop.get("label") or key.replace("_", " ").title())
        fields.append(
            {
                "key": path,
                "label": label,
                "type": "choice" if choice_pairs else type_name,
                "default": prop.get("default"),
                "description": str(prop.get("description") or ""),
                "required": key in required,
                "choices": choice_pairs,
                "min": prop.get("minimum", prop.get("exclusiveMinimum")),
                "max": prop.get("maximum", prop.get("exclusiveMaximum")),
                "section": str(prop.get("section") or "General"),
                "advanced": bool(prop.get("advanced")),
            }
        )
    return fields


@lru_cache(maxsize=None)
def form_fields(attack_id: str) -> List[Dict[str, Any]]:
    """Flatten a technique's pydantic JSON schema into form fields."""
    from hackagent.orchestrator.registry import load_config_model

    model = load_config_model(attack_id)
    if model is None or not hasattr(model, "model_json_schema"):
        return []
    schema = model.model_json_schema()
    defs = schema.get("$defs") or {}
    return _form_fields_from_schema(schema, defs, prefix="")


@lru_cache(maxsize=1)
def catalog_entries() -> List[Dict[str, Any]]:
    """Registered techniques, in registry order, with form fields.

    Command lists and TUI forms are generated from this. It includes every
    registry id, including techniques that are absent from older hand-written
    catalogs.
    """
    from hackagent.catalog.attacks import ATTACK_CATALOG
    from hackagent.catalog.taxonomy import get_attack_taxonomy
    from hackagent.orchestrator.registry import ATTACK_REGISTRY

    primary = _primary_orders()
    entries: List[Dict[str, Any]] = []
    for attack_id in ATTACK_REGISTRY:
        meta = ATTACK_CATALOG.get(attack_id, {})
        taxonomy = get_attack_taxonomy(attack_id)
        label = meta.get("label") or attack_id
        entries.append(
            {
                "attack_type": attack_id,
                "label": label,
                "description": meta.get("description", ""),
                "category": taxonomy.category.value,
                "category_label": taxonomy.category.label,
                "category_description": taxonomy.category.description,
                "tags": list(taxonomy.tag_values()),
                "tag_labels": [tag.label for tag in taxonomy.tags],
                "primary_order": primary.get(attack_id),
                "fields": form_fields(attack_id),
            }
        )
    return entries


def catalog_by_id() -> Dict[str, Dict[str, Any]]:
    return {entry["attack_type"]: entry for entry in catalog_entries()}


def grouped_catalog() -> List[tuple[str, str, List[Dict[str, Any]]]]:
    """``(category, category_label, entries)`` in taxonomy order."""
    buckets: Dict[str, List[Dict[str, Any]]] = {key: [] for key in _CATEGORY_ORDER}
    labels: Dict[str, str] = {}
    for entry in catalog_entries():
        buckets.setdefault(entry["category"], []).append(entry)
        labels[entry["category"]] = entry["category_label"]
    grouped: List[tuple[str, str, List[Dict[str, Any]]]] = []
    for category in list(_CATEGORY_ORDER) + [
        key for key in buckets if key not in _CATEGORY_ORDER
    ]:
        entries = buckets.get(category) or []
        if entries:
            grouped.append((category, labels.get(category, category), entries))
    return grouped


def plan_attack(target: Dict[str, Any], **kwargs: Any) -> Any:
    """Choose a technique, goals and parameters for ``target``."""
    from hackagent.orchestrator.planning import plan_attack as _plan_attack

    return _plan_attack(target, **kwargs)


def web_target(url: str, **kwargs: Any) -> tuple[str, Dict[str, Any]]:
    """Build the ``("web", operational_config)`` pair for a live-browser chatbot."""
    from hackagent.orchestrator.planning import build_web_target

    return build_web_target(url, **kwargs)


def result_bucket(status: Optional[str], notes: Optional[str] = None) -> str:
    """Classify a result the same way the store does.

    Interfaces use this instead of importing storage bucket constants.
    """
    from hackagent.storage.buckets import result_bucket as _bucket

    return _bucket(status, notes)


def ensure_graphviz(*, allow_download: bool = False) -> Optional[str]:
    """Locate or install the Graphviz ``dot`` binary used by FC-Attack."""
    from hackagent.attacks._lib.graphviz import ensure_graphviz as _ensure

    return _ensure(allow_download=allow_download)


def __getattr__(name: str) -> Any:
    if name in {"DEFAULT_PLANNER_MODEL", "PlannerError"}:
        from hackagent.orchestrator import planning

        value = getattr(planning, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# Bound target
# ---------------------------------------------------------------------------


_TARGET_SPEC_FIELDS = ("max_tokens", "temperature", "top_p", "timeout", "thinking")
_TARGET_METADATA_KEYS = (
    "api_key",
    "max_tokens",
    "temperature",
    "top_p",
    "top_k",
    "num_ctx",
    "stream",
    "timeout",
    "thinking",
    "tools",
    "tool_choice",
    "extra_body",
    "reasoning_effort",
)


def _resolve_target_config(target_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    from hackagent.attacks.techniques.config import default_target

    resolved = default_target()
    if not target_config:
        return resolved
    merged = {key: value for key, value in target_config.items() if value is not None}
    if "request_timeout" in merged and "timeout" not in merged:
        merged["timeout"] = merged.pop("request_timeout")
    resolved.update(merged)
    return resolved


def _target_spec(
    *,
    name: str,
    endpoint: str,
    agent_type: AgentType,
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Any:
    from hackagent.core.contracts import ModelSpec

    flat = {key: metadata[key] for key in _TARGET_METADATA_KEYS if key in metadata}
    flat.update({key: value for key, value in config.items() if value is not None})
    model_name = flat.pop("name", None) or metadata.get("name") or name
    if agent_type == AgentType.GOOGLE_ADK:
        model_name = name
    fields: Dict[str, Any] = {
        key: flat.pop(key) for key in _TARGET_SPEC_FIELDS if key in flat
    }
    return ModelSpec(
        identifier=str(model_name),
        endpoint=flat.pop("endpoint", None) or endpoint or None,
        agent_type=agent_type,
        api_key=flat.pop("api_key", None) or None,
        extra=flat,
        **fields,
    )


class Target:
    """One victim bound to a :class:`HackAgent` session."""

    def __init__(
        self,
        session: "HackAgent",
        endpoint: str,
        agent_type: Union[AgentType, str] = AgentType.UNKNOWN,
        *,
        name: Optional[str] = None,
        guardrails: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        target_config: Optional[Dict[str, Any]] = None,
        adapter_operational_config: Optional[Dict[str, Any]] = None,
        thinking: Optional[bool] = None,
    ) -> None:
        from hackagent.attacks._lib.llm_router import LLMRouter
        from hackagent.models.client import connect
        from hackagent.models.dispatch import check_supported
        from hackagent.models.factory import ModelFactory, spec_from_config
        from hackagent.models.guardrail import Guarded, GuardrailSpec, LLMGuardrail

        self.session = session
        self.settings = session.settings
        self.backend = session.backend
        processed = AgentType.parse(agent_type)
        self.target_config = _resolve_target_config(target_config)
        explicit_target_config = (
            {
                key: value
                for key, value in (target_config or {}).items()
                if value is not None
            }
            if target_config
            else {}
        )
        router_metadata = {
            key: value
            for key, value in {**(metadata or {}), **explicit_target_config}.items()
            if value is not None
        }
        router_operational_config = {
            **self.target_config,
            **(adapter_operational_config or {}),
        }
        if processed == AgentType.OLLAMA:
            if (
                thinking is not None
                and router_operational_config.get("thinking") is None
            ):
                router_operational_config["thinking"] = thinking
        else:
            router_operational_config.pop("thinking", None)

        check_supported(processed)
        self.models = ModelFactory(self.settings)
        context = self.backend.get_context()
        self.organization_id = context.org_id
        if processed == AgentType.GOOGLE_ADK:
            router_operational_config.setdefault("user_id", context.user_id)
        self.target_spec = _target_spec(
            name=name or endpoint,
            endpoint=endpoint,
            agent_type=processed,
            metadata=router_metadata,
            config=router_operational_config,
        )
        self.agent_record = self.backend.create_or_update_agent(
            name=name or endpoint,
            agent_type=processed.value,
            endpoint=endpoint,
            metadata=router_metadata,
            overwrite_metadata=True,
        )
        self.agent_id = self.agent_record.id

        before_guardrail, after_guardrail = _guardrail_sides(guardrails)
        self.guardrails: Dict[str, Any] = {}
        for side, guardrail_config in (
            ("before", before_guardrail),
            ("after", after_guardrail),
        ):
            if guardrail_config:
                self.guardrails[side] = spec_from_config(
                    guardrail_config, spec_type=GuardrailSpec
                )
                logger.info("%s guardrail active on the target.", side)
        self.target = connect(self.target_spec, instance_id=str(self.agent_record.id))
        if self.guardrails:
            self.target = Guarded(
                self.target,
                before=self._build_guardrail("before", LLMGuardrail),
                after=self._build_guardrail("after", LLMGuardrail),
            )
        self.router = LLMRouter(self.target, agent=self.agent_record)

    def _build_guardrail(self, side: str, guardrail_cls: type) -> Any:
        spec = self.guardrails.get(side)
        if spec is None:
            return None
        return guardrail_cls(
            self.models.for_role(spec), system_prompt=spec.system_prompt
        )

    def hack(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]] = None,
        fail_on_run_error: bool = True,
        on_event: Optional[Any] = None,
    ) -> Any:
        """Run one attack. ``on_event`` receives ``(event_type, **payload)``."""
        try:
            from hackagent.orchestrator.runner import run as run_attack

            attack_type = attack_config.get("attack_type")
            if not attack_type:
                raise ValueError("'attack_type' must be provided in attack_config.")
            logger.info(
                "Preparing to attack agent '%s' (ID: %s, Type: %s) using strategy '%s'.",
                self.agent_record.name,
                self.agent_record.id,
                self.agent_record.agent_type,
                attack_type,
            )
            return run_attack(
                self,
                attack_config,
                run_config_override=run_config_override,
                fail_on_run_error=fail_on_run_error,
                _tui_event_bus=_as_bus(on_event),
            )
        except HackAgentError:
            raise
        except ValueError as exc:
            logger.error("Configuration error in HackAgent.hack: %s", exc, exc_info=True)
            raise HackAgentError(f"Configuration error: {exc}") from exc
        except RuntimeError as exc:
            logger.error("Runtime error during HackAgent.hack: %s", exc, exc_info=True)
            if "Failed to create backend agent" in str(
                exc
            ) or "Failed to update metadata" in str(exc):
                raise HackAgentError(f"Backend agent operation failed: {exc}") from exc
            raise HackAgentError(f"An unexpected runtime error occurred: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in HackAgent.hack: %s", exc, exc_info=True)
            raise HackAgentError(
                f"An unexpected error occurred during attack: {exc}"
            ) from exc

    def hack_chain(
        self,
        attacks: Optional[list] = None,
        goals: Optional[list] = None,
        run_config_override: Optional[Dict[str, Any]] = None,
        fail_on_run_error: bool = True,
        escalate_only_mitigated: bool = True,
        on_event: Optional[Any] = None,
    ) -> list:
        """Run a sequence of attacks. ``on_event`` is forwarded to each step."""
        from hackagent.orchestrator.chain import hack_chain as _hack_chain

        return _hack_chain(
            self,
            attacks=attacks,
            goals=goals,
            run_config_override=run_config_override,
            fail_on_run_error=fail_on_run_error,
            escalate_only_mitigated=escalate_only_mitigated,
            on_event=on_event,
        )


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DoctorReport:
    """Structured diagnostics for ``hackagent doctor``."""

    config_path: str
    config_exists: bool
    db_path: str
    db_exists: bool
    api_key_set: bool
    pandas_available: bool
    yaml_available: bool
    graphviz_dot: Optional[str]
    graphviz_error: Optional[str]
    issues: tuple[str, ...]


class HackAgent:
    """Session over settings and a store. Bind a victim with :meth:`target`."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        backend: Any = None,
        timeout: Optional[float] = 120.0,
        raise_on_unexpected_status: bool = False,
    ) -> None:
        self.settings = settings if settings is not None else Settings.resolve()
        self.backend = _open_store(
            self.settings,
            backend=backend,
            timeout=timeout,
            raise_on_unexpected_status=raise_on_unexpected_status,
        )

    def close(self) -> None:
        closer = getattr(self.backend, "close", None)
        if callable(closer):
            closer()

    def target(
        self,
        endpoint: str,
        agent_type: Union[AgentType, str] = AgentType.UNKNOWN,
        *,
        name: Optional[str] = None,
        guardrails: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        target_config: Optional[Dict[str, Any]] = None,
        adapter_operational_config: Optional[Dict[str, Any]] = None,
        thinking: Optional[bool] = None,
    ) -> Target:
        """Bind ``endpoint`` and return an object with ``hack`` and ``hack_chain``."""
        return Target(
            self,
            endpoint,
            agent_type,
            name=name,
            guardrails=guardrails,
            metadata=metadata,
            target_config=target_config,
            adapter_operational_config=adapter_operational_config,
            thinking=thinking,
        )

    # -- reads ----------------------------------------------------------------

    def context(self) -> Any:
        return self.backend.get_context()

    def agents(self, *, page: int = 1, page_size: int = 100) -> Any:
        return self.backend.list_agents(page=page, page_size=page_size)

    def agent(self, agent_id: Any) -> Any:
        return self.backend.get_agent(_as_uuid(agent_id))

    def attacks(self, *, page: int = 1, page_size: int = 100) -> Any:
        return self.backend.list_attacks(page=page, page_size=page_size)

    def runs(
        self,
        *,
        attack_id: Any = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Any:
        return self.backend.list_runs(
            attack_id=_as_uuid(attack_id) if attack_id else None,
            page=page,
            page_size=page_size,
        )

    def run(self, run_id: Any) -> Any:
        return self.backend.get_run(_as_uuid(run_id))

    def results(
        self,
        *,
        run_id: Any = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Any:
        return self.backend.list_results(
            run_id=_as_uuid(run_id) if run_id else None,
            page=page,
            page_size=page_size,
        )

    def result(self, result_id: Any) -> Any:
        return self.backend.get_result(_as_uuid(result_id))

    def traces(self, result_id: Any) -> List[Any]:
        return self.backend.list_traces(_as_uuid(result_id))

    def delete_run(self, run_id: Any) -> None:
        """Delete one run. This is a write; reads never call it."""
        self.backend.delete_run(_as_uuid(run_id))

    # -- discovery -------------------------------------------------------------

    def catalog(self) -> List[Dict[str, Any]]:
        return catalog_entries()

    def presets(self) -> Dict[str, Dict[str, Any]]:
        return presets()

    def load_goals(self, **kwargs: Any) -> List[Any]:
        return load_goals(**kwargs)

    def plan_attack(self, target: Dict[str, Any], **kwargs: Any) -> Any:
        return plan_attack(target, **kwargs)

    def check_connection(self) -> int:
        """Probe the remote API. Local sessions return ``0``."""
        probe = getattr(self.backend, "check_connection", None)
        if not callable(probe):
            return 0
        return int(probe())

    def ensure_graphviz(self, *, allow_download: bool = False) -> Optional[str]:
        return ensure_graphviz(allow_download=allow_download)

    def doctor(self) -> DoctorReport:
        """Collect configuration diagnostics, including Graphviz."""
        config_path = Path(self.settings.config_path)
        db_path = Path(self.settings.db_path) if self.settings.db_path != ":memory:" else None
        issues: list[str] = []
        config_exists = config_path.exists()
        if not config_exists:
            issues.append("No configuration file found")
        db_exists = bool(db_path and db_path.exists())
        pandas_available = importlib.util.find_spec("pandas") is not None
        yaml_available = importlib.util.find_spec("yaml") is not None
        if not pandas_available:
            issues.append("pandas is not installed")
        dot: Optional[str] = None
        graphviz_error: Optional[str] = None
        try:
            dot = self.ensure_graphviz(allow_download=False)
        except Exception as exc:
            graphviz_error = str(exc)
        return DoctorReport(
            config_path=str(config_path),
            config_exists=config_exists,
            db_path=str(db_path) if db_path else ":memory:",
            db_exists=db_exists,
            api_key_set=bool(self.settings.api_key),
            pandas_available=pandas_available,
            yaml_available=yaml_available,
            graphviz_dot=dot,
            graphviz_error=graphviz_error,
            issues=tuple(issues),
        )


__all__ = [
    "DoctorReport",
    "HackAgent",
    "Target",
    "catalog_by_id",
    "catalog_entries",
    "ensure_graphviz",
    "form_fields",
    "grouped_catalog",
    "load_goals",
    "plan_attack",
    "preset",
    "presets",
    "primary_attacks",
    "primary_dataset",
    "result_bucket",
    "web_target",
]
