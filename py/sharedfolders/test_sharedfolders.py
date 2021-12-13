#!/usr/bin/python3 -m unittest

import unittest
import mock

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import sharedfolders


matrix = {
    "fprint": {
        "source": "one",
        "target": "two",
        "folder": "/home/user",
        "response": sharedfolders.RESPONSE_ALLOW_ALWAYS,
    },
    "fprint2": {
        "source": "one",
        "target": "two",
        "folder": "/home",
        "response": sharedfolders.RESPONSE_DENY_ALWAYS,
    },
}


class TestDecisions(unittest.TestCase):
    def test_subfolder(self):
        global matrix
        source, target = "one", "two"
        decision, fingerprint = sharedfolders.lookup_decision_in_matrix(
            matrix, source, target, "/home/user/subfolder"
        )
        assert decision["response"] == sharedfolders.RESPONSE_ALLOW_ALWAYS
        assert fingerprint == "fprint"

    def test_not_authorized(self):
        global matrix
        source, target = "one", "two"
        decision, fingerprint = sharedfolders.lookup_decision_in_matrix(
            matrix, source, target, "/hom"
        )
        assert decision == None
        assert fingerprint not in matrix

    def test_exact(self):
        global matrix
        source, target = "one", "two"
        decision, fingerprint = sharedfolders.lookup_decision_in_matrix(
            matrix, source, target, "/home"
        )
        assert decision["response"] == sharedfolders.RESPONSE_DENY_ALWAYS, response
        assert fingerprint == "fprint2"
