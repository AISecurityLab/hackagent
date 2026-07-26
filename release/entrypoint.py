# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PyInstaller entry point mirroring the ``hackagent`` console script."""

from hackagent.cli.main import cli

if __name__ == "__main__":
    cli()
