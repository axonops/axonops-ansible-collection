#!/usr/bin/env python3
"""Front end for the AxonOps Configurations Exporter.

All the logic lives in the `src` package; this file only wires the command line
into `src.application.Application`. Run it as a script:

    python3 configurations_exporter.py --help
"""

import sys

from src.application import Application


def main() -> int:
    return Application().run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
