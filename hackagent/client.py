# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Facade (depth 2).

``HackAgent`` is constructed from :class:`~hackagent.core.settings.Settings`
and reads what past runs recorded: campaigns, runs, results, agents and the
catalogs. Running an attack is a campaign —
:func:`~hackagent.orchestrator.campaign.run_campaign` — and there is no
second way to do it. Interfaces talk only to this module and the public
types re-exported from :mod:`hackagent`.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from hackagent.core.contracts import AgentType
from hackagent.core.logging import get_logger
from hackagent.core.credentials import CredentialError
from hackagent.core.settings import Mode, Settings

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
        logger.info(
            "HackAgent using caller-provided backend %s", type(backend).__name__
        )
        return backend
    if settings.mode is Mode.REMOTE:
        from hackagent.storage.remote import RemoteBackend

        if not settings.api_key:
            raise CredentialError(
                "Remote storage requires a HackAgent platform API key."
            )

        logger.info("HackAgent using remote backend → %s", settings.base_url)
        return RemoteBackend.connect(
            settings.base_url,
            settings.api_key,
            timeout=timeout,
            raise_on_unexpected_status=raise_on_unexpected_status,
            verify=settings.verify,
        )
    from hackagent.storage.local import LocalBackend

    logger.info(
        "HackAgent using local backend → %s. Pass backend='remote' "
        "(or set HACKAGENT_BACKEND=remote) to enable remote tracking.",
        settings.db_path,
    )
    return LocalBackend(db_path=settings.db_path)


def _as_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


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
    """Jailbreak campaign technique ids ``hack`` can execute, in order.

    Both halves count: a migrated technique runs on the campaign runner and
    the rest on the legacy pipeline. A technique neither can run is dropped,
    so a chain built from this never fails on its first step.
    """
    from hackagent.attacks.techniques.registry import ATTACKS

    runnable = ATTACKS
    return [
        attack_id
        for attack_id, _index in sorted(
            _primary_orders().items(), key=lambda item: item[1]
        )
        if attack_id in runnable
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
    from hackagent.attacks.techniques.registry import params_schema

    schema = params_schema(attack_id)
    if schema is None:
        return []
    defs = schema.get("$defs") or {}
    return _form_fields_from_schema(schema, defs, prefix="")


@lru_cache(maxsize=1)
def catalog_entries() -> List[Dict[str, Any]]:
    """Registered techniques, in registry order, with form fields.

    Command lists and TUI forms are generated from this. It covers both
    halves of the migration — what the legacy pipeline still runs and what
    the campaign runner has taken over — because ``hack`` runs either.
    """
    from hackagent.attacks.techniques.registry import ATTACKS
    from hackagent.catalog.attacks import ATTACK_CATALOG
    from hackagent.catalog.taxonomy import get_attack_taxonomy

    primary = _primary_orders()
    entries: List[Dict[str, Any]] = []
    # Legacy ids keep their registry order; migrated ones follow, so a
    # technique stays selectable for the whole of its migration.
    for attack_id in sorted(ATTACKS):
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


_TARGET_SPEC_FIELDS = (
    "max_tokens",
    "temperature",
    "top_p",
    "timeout",
    "thinking",
    "capabilities",
)
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
    from hackagent.models.target_params import default_target

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
        api_key=flat.pop("api_key", None),
        extra=flat,
        **fields,
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

    def campaign_runs(self, *, page: int = 1, page_size: int = 100) -> Any:
        """List campaign-level runs, including their audit reports."""

        return self.backend.list_campaign_runs(page=page, page_size=page_size)

    def campaign_run(self, campaign_run_id: Any) -> Any:
        """Retrieve one campaign run and its immutable specification/audit."""

        return self.backend.get_campaign_run(_as_uuid(campaign_run_id))

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
        db_path = (
            Path(self.settings.db_path) if self.settings.db_path != ":memory:" else None
        )
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
