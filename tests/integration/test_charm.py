#!/usr/bin/env python3
# Copyright 2025 Dwellir
# See LICENSE file for licensing details.

from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]


@pytest.mark.abort_on_fail
async def test_build_charm(ops_test: OpsTest):
    """Build the charm-under-test from local source."""
    charm_path = await ops_test.build_charm(".")

    assert APP_NAME == "polkadot"
    assert charm_path.exists()
