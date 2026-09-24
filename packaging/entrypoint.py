# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Entry point for the frozen ``hackagent`` binary."""

import multiprocessing

from hackagent.interfaces.cli.safe_stdio import configure_safe_stdio

if __name__ == "__main__":
    multiprocessing.freeze_support()
    # Configure stdio before importing the CLI so import-time Rich/Click
    # writes cannot crash a cp1252 Windows console.
    configure_safe_stdio()
    from hackagent.interfaces.cli.main import main

    main()
