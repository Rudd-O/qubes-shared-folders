#!/usr/bin/python3 -m unittest

import json
import os
import sys
import tempfile
import unittest

import sharedfolders


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


matrix = sharedfolders.DecisionMatrix(
    {
        "fprint": sharedfolders.Decision(
            "one",
            "two",
            "/home/user",
            sharedfolders.RESPONSES.ALLOW_ALWAYS,
        ),
        "fprint2": sharedfolders.Decision(
            "one",
            "two",
            "/home",
            sharedfolders.RESPONSES.DENY_ALWAYS,
        ),
        "fprint3": sharedfolders.Decision(
            "one",
            "two",
            "/var",
            sharedfolders.RESPONSES.ALLOW_ALWAYS,
        ),
        "fprint4": sharedfolders.Decision(
            "one",
            "two",
            "/var/lib",
            sharedfolders.RESPONSES.DENY_ALWAYS,
        ),
    }
)


class TestDecisions(unittest.TestCase):
    def test_subfolder(self) -> None:
        global matrix
        source, target = "one", "two"
        decision, fingerprint = matrix.lookup_decision(
            source, target, "/home/user/subfolder"
        )
        assert (
            decision is not None
            and decision.response is sharedfolders.RESPONSES.ALLOW_ALWAYS
        ), decision
        assert fingerprint == "fprint"

    def test_not_authorized(self) -> None:
        global matrix
        source, target = "one", "two"
        decision, fingerprint = matrix.lookup_decision(source, target, "/hom")
        assert decision is None
        assert fingerprint not in matrix

    def test_exact(self) -> None:
        global matrix
        source, target = "one", "two"
        decision, fingerprint = matrix.lookup_decision(source, target, "/home")
        assert (
            decision is not None
            and decision.response is sharedfolders.RESPONSES.DENY_ALWAYS
        ), decision
        assert fingerprint == "fprint2"

    def test_parent_folder_allowed_even_when_subfolder_denied(self) -> None:
        global matrix
        source, target = "one", "two"
        decision, fingerprint = matrix.lookup_decision(source, target, "/var")
        assert (
            decision is not None
            and decision.response is sharedfolders.RESPONSES.ALLOW_ALWAYS
        ), decision
        assert fingerprint == "fprint3"

    def test_subfolder_allowed_by_parent_even_when_it_denied(self) -> None:
        global matrix
        source, target = "one", "two"
        decision, fingerprint = matrix.lookup_decision(source, target, "/var/lib")
        assert (
            decision is not None
            and decision.response is sharedfolders.RESPONSES.ALLOW_ALWAYS
        ), decision
        assert fingerprint == "fprint3"

    def test_vm_mismatch(self) -> None:
        global matrix
        source, target = "one", "three"
        decision, fingerprint = matrix.lookup_decision(source, target, "/var/lib")
        assert decision is None, decision
        assert fingerprint == "a9b00af7d077959658b57b755fc32c1d", fingerprint


class TestDecisionMatrixLoad(unittest.TestCase):
    def test_loads(self) -> None:
        global matrix
        old = matrix.POLICY_DB
        try:
            with tempfile.NamedTemporaryFile() as t:
                matrix.__class__.POLICY_DB = t.name
                matrix.POLICY_DB = t.name
                matrix.save()
                matrix.load()
        finally:
            matrix.POLICY_DB = old
