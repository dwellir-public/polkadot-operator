# Copyright 2021 dwellir
# See LICENSE file for licensing details.

import unittest
# from unittest.mock import Mock

from ops.testing import Harness
from charm import PolkadotCharm


class TestCharm(unittest.TestCase):
    def test_config_changed(self):
        harness = Harness(Polkadot  Charm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        self.assertEqual(harness.charm._stored.validator_name, "Dwellir")
        harness.update_config({"validator-name": "NameChanged"})
        self.assertEqual(harness.charm._stored.validator_name, "NameChanged")
