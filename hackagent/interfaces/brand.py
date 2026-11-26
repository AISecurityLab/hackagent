# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What HackAgent says about itself, the same in every interface: the logo,
the line under it, and the way through a first campaign.

The TUI's welcome screen and the command line (``hackagent --help``,
``init``, ``version``) show these and nothing of their own; the logo's
colour is the palette's :data:`~hackagent.interfaces.palette.BRAND`.
"""

from __future__ import annotations

#: The logo, as line art.
BANNER = """\
██╗  ██╗ █████╗  ██████╗██╗  ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
███████║███████║██║     █████╔╝ ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
██╔══██║██╔══██║██║     ██╔═██╗ ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
██║  ██║██║  ██║╚██████╗██║  ██╗██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝"""

#: What HackAgent is, in one line: under the logo, in the package's
#: description, in the docs.
TAGLINE = "The open-source red-team toolkit for AI models and agents"

#: A first campaign from the command line, step by step: what the welcome
#: screen does with its buttons. Each step is what it does and the command.
QUICK_START: tuple[tuple[str, str], ...] = (
    ("Pick an example", "hackagent examples list"),
    ("Copy it to edit", "hackagent examples copy NAME campaign.yaml"),
    ("Check it", "hackagent campaign validate campaign.yaml"),
    ("Run it", "hackagent campaign run campaign.yaml"),
    ("See what it found", "hackagent results summary"),
)

#: The same, in the terminal app.
APP = ("Or all of it in the app", "hackagent")

__all__ = ["APP", "BANNER", "QUICK_START", "TAGLINE"]
