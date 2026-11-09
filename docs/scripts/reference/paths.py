# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Where pages live on the docs site, so every generator links the same way.

Page keys are paths relative to ``docs/docs`` without the extension, such as
``cli/campaign-files/target`` or ``attacks/adaptive/pair``.
"""

from __future__ import annotations

import posixpath

#: The generated campaign-format pages.
CAMPAIGN_FILES = "cli/campaign-files"


def attack_type(name: str) -> str:
    """The folder an attack's page sits in, from its registry module path.

    ``multi_turn`` becomes ``multi-turn``, so URLs use hyphens like every
    other page.
    """
    from hackagent.attacks.techniques.registry import attack_family

    family = attack_family(name)
    if family is None:
        raise ValueError(f"{name!r} is not a registered attack")
    return family.replace("_", "-")


def type_label(folder: str) -> str:
    """How an attack type is named in tables: ``multi-turn`` -> ``Multi-turn``."""
    return folder.capitalize()


def attack_page(name: str) -> str:
    """The hand-written page that explains an attack."""
    return f"attacks/{attack_type(name)}/{name}"


def relative(from_page: str, to: str) -> str:
    """A link from one page key to a file path, both relative to ``docs/docs``."""
    return posixpath.relpath(to, posixpath.dirname(from_page) or ".")
