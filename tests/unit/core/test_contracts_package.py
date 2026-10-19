# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``hackagent.core.contracts`` re-exports every topic module's names."""

import importlib
import pkgutil

import hackagent.core.contracts as contracts


def _topic_modules():
    for info in pkgutil.iter_modules(contracts.__path__):
        if not info.name.startswith("_"):
            yield importlib.import_module(f"{contracts.__name__}.{info.name}")


def test_package_exports_exactly_the_topic_modules_names():
    topic_names = set()
    for module in _topic_modules():
        for name in module.__all__:
            assert getattr(contracts, name) is getattr(module, name)
        topic_names.update(module.__all__)
    assert set(contracts.__all__) == topic_names


def test_topic_modules_do_not_export_the_same_name_twice():
    seen = {}
    for module in _topic_modules():
        for name in module.__all__:
            assert name not in seen, f"{name} in {seen.get(name)} and {module.__name__}"
            seen[name] = module.__name__
