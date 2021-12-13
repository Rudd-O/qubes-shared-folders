#!/usr/bin/python3 -m unittest

import unittest
import mock

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import sharedfolders


class TestDecisions(unittest.TestCase):
    def test_decisions(self):
        source = "one"
        target = "two"
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
        response, fingerprint = sharedfolders.lookup_decision_response_in_matrix(
            matrix, source, target, "/home/user/subfolder"
        )
        assert response == sharedfolders.RESPONSE_ALLOW_ALWAYS
        assert fingerprint == "fprint"
        response, fingerprint = sharedfolders.lookup_decision_response_in_matrix(
            matrix, source, target, "/hom"
        )
        assert response == None
        assert fingerprint not in matrix
        response, fingerprint = sharedfolders.lookup_decision_response_in_matrix(
            matrix, source, target, "/home"
        )
        assert response == sharedfolders.RESPONSE_DENY_ALWAYS, response
        assert fingerprint == "fprint2"
