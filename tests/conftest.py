import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-hardware",
        action="store_true",
        default=False,
        help="run hardware integration tests that require optional dependencies and devices",
    )


def pytest_collection_modifyitems(config, items):
    run_hardware = config.getoption("--run-hardware") or os.getenv("RUN_HARDWARE_TESTS") == "1"
    if run_hardware:
        return

    skip_hardware = pytest.mark.skip(
        reason="hardware tests are disabled by default; use --run-hardware or RUN_HARDWARE_TESTS=1"
    )
    for item in items:
        if "hardware" in item.keywords:
            item.add_marker(skip_hardware)
