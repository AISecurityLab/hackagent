# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Entry point for the frozen ``hackagent`` binary."""

import multiprocessing

from hackagent.cli.main import cli

if __name__ == "__main__":
    multiprocessing.freeze_support()
    cli()
