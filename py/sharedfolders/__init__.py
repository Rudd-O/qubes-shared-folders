#!/usr/bin/python3

import base64
import errno
import glob
import hashlib
import json
import logging
import os
import subprocess
import sys
from typing import Literal, Optional, Tuple, Dict, TypeVar, Type, Any


class Response(object):
    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return "<Response " + self.name + " %s>" % id(self)

    def startswith(self, prefix: str) -> bool:
        return self.name.startswith(prefix)


RESPONSE_ALLOW_ONETIME = Response("ALLOW_ONETIME")
RESPONSE_DENY_ONETIME = Response("DENY_ONETIME")
RESPONSE_ALLOW_ALWAYS = Response("ALLOW_ALWAYS")
RESPONSE_DENY_ALWAYS = Response("DENY_ALWAYS")
RESPONSE_BLOCK = Response("BLOCK")
RESPONSES: Dict[str, Response] = dict(
    [
        (str(x), x)
        for x in (
            RESPONSE_ALLOW_ONETIME,
            RESPONSE_DENY_ONETIME,
            RESPONSE_ALLOW_ALWAYS,
            RESPONSE_DENY_ALWAYS,
            RESPONSE_BLOCK,
        )
    ]
)
RESPONSE_ALLOW_PREFIX = "ALLOW"
RESPONSE_DENY_PREFIX = "DENY"


logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO if os.getenv("DEBUG") else logging.WARNING)


def contains(needle: str, haystack: str) -> bool:
    """Check if the needle path is contained in the haystack path."""
    needle = os.path.abspath(needle)
    haystack = os.path.abspath(haystack)
    if not needle.endswith(os.path.sep):
        needle = needle + os.path.sep
    if not haystack.endswith(os.path.sep):
        haystack = haystack + os.path.sep
    if needle == haystack:
        return True
    if (needle).startswith(haystack):
        return True
    return False


def check_target_is_dom0() -> bool:
    return (
        os.getenv("QREXEC_REQUESTED_TARGET_TYPE") == "name"
        and os.getenv("QREXEC_REQUESTED_TARGET") == "dom0"
    ) or (
        os.getenv("QREXEC_REQUESTED_TARGET_TYPE") == "keyword"
        and os.getenv("QREXEC_REQUESTED_TARGET_KEYWORD") == "adminvm"
    )


def base_to_str(binarydata: bytes) -> str:
    data = base64.b64decode(binarydata)
    return data.decode("utf-8")


def fingerprint_decision(source: str, target: str, folder: str) -> str:
    fingerprint = hashlib.sha256()
    fingerprint.update(source.encode("utf-8"))
    fingerprint.update(b"\0")
    fingerprint.update(target.encode("utf-8"))
    fingerprint.update(b"\0")
    fingerprint.update(folder.encode("utf-8"))
    fingerprint.update(b"\0")
    return fingerprint.hexdigest()[:32]


class Decision(object):
    source: str = ""
    target: str = ""
    folder: str = ""
    response: Response = RESPONSE_DENY_ALWAYS

    def __init__(self, source: str, target: str, folder: str, response: Response):
        self.source = source
        self.target = target
        self.folder = folder
        assert response in RESPONSES.values()
        self.response = response

    def toJSON(self) -> str:
        return json.dumps(self.__dict__)


DMT = TypeVar("DMT", bound="DecisionMatrix")


class DecisionMatrix(Dict[str, Decision]):
    POLICY_DB = "/etc/qubes/shared-folders/policy.db"

    @classmethod
    def load(klass: Type[DMT]) -> DMT:
        def hook(obj: Dict[Any, Any]) -> Any:
            if "folder" in obj:
                return Decision(
                    source=obj["source"],
                    target=obj["target"],
                    folder=obj["folder"],
                    response=RESPONSES[obj["response"]],
                )
            else:
                return DecisionMatrix(obj)

        try:
            with open(klass.POLICY_DB, "r") as db:
                data = json.load(db, object_hook=hook)
            self = klass()
            for k, v in data.items():
                self[k] = v
            return self
        except Exception:
            return klass()

    def save(self) -> None:
        class DecisionMatrixEncoder(json.JSONEncoder):
            def default(self, obj: Any) -> Any:
                if isinstance(obj, Decision):
                    return obj.__dict__
                if isinstance(obj, Response):
                    return str(obj)
                return json.JSONEncoder.default(self, obj)

        with open(self.POLICY_DB + ".tmp", "w") as db:
            json.dump(self, db, indent=4, sort_keys=True, cls=DecisionMatrixEncoder)
        os.chmod(self.POLICY_DB + ".tmp", 0o664)
        os.rename(self.POLICY_DB + ".tmp", self.POLICY_DB)

    def revoke_onetime_accesses_for_fingerprint(self, fingerprint: str) -> None:
        """This method mutates the internal state and updates the policy on disk."""
        if fingerprint in self and self[fingerprint].response in (
            RESPONSE_DENY_ONETIME,
            RESPONSE_ALLOW_ONETIME,
        ):
            logger.info(
                "One-time decision expired for %s, applying policy changes", fingerprint
            )
            del self[fingerprint]
            ConnectToFolderPolicy.apply_policy_changes_from(self)
            self.save()

    def lookup_decision(
        self, source: str, target: str, folder: str
    ) -> Tuple[Optional[Decision], str]:
        """Look up a decision in the table for src->dst VMs, from most specific to least specific.

        If no decision is made, prospectively generate a fingerprint for this decision to use later.
        """
        matches = []
        for fingerprint, decision in self.items():
            if (
                source == decision.source
                and target == decision.target
                and contains(folder, decision.folder)
            ):
                matches.append((fingerprint, decision))
        if matches:
            for fingerprint, match in reversed(
                sorted(matches, key=lambda m: len(m[1].folder))
            ):
                if match.response.startswith(RESPONSE_ALLOW_PREFIX):
                    break
            return match, fingerprint
        fingerprint = fingerprint_decision(source, target, folder)
        return None, fingerprint

    def lookup_prior_authorization(
        self, source: str, target: str, folder: str
    ) -> Tuple[Optional[Response], str]:
        """Called by the client qube during AuthorizeFolderAccess before
        process_authorization_request.

        This method mutates the internal state and updates the policy on disk."""
        match, fingerprint = self.lookup_decision(source, target, folder)
        self.revoke_onetime_accesses_for_fingerprint(fingerprint)
        return (
            (match.response, fingerprint)
            if match
            and match.response
            not in (
                RESPONSE_ALLOW_ONETIME,
                RESPONSE_DENY_ONETIME,
            )
            else (None, fingerprint)
        )

    def process_authorization_request(
        self, source: str, target: str, folder: str, response: Response
    ) -> str:
        """Called by the client qube during AuthorizeFolderAccess, after
        lookup_prior_authorization.

        This method mutates the internal state and updates the policy on disk."""
        if response is RESPONSE_BLOCK:
            # The user means to block ALL, so we transform this into
            # a complete block for the machine, by blocking the root
            # directory, which means to block absolutely everything.
            response = RESPONSE_DENY_ALWAYS
            folder = "/"
        fingerprint = fingerprint_decision(source, target, folder)
        decision = Decision(source, target, folder, response)
        self[fingerprint] = decision
        ConnectToFolderPolicy.apply_policy_changes_from(self)
        self.save()
        return fingerprint

    def lookup_decision_folder(
        self, fingerprint: str, requested_folder: str
    ) -> Optional[str]:
        """Called by the server qube during ConnectToFolder to verify the
        folder is a subfolder or is the same as the folder the client qube
        is authorized to access.

        The client qube has already connected to the server qube here.

        This method mutates the internal state and updates the policy on disk."""
        match = self.get(fingerprint)
        self.revoke_onetime_accesses_for_fingerprint(fingerprint)
        if match and contains(requested_folder, match.folder):
            logger.info(
                "Requested folder %s is contained in folder %s", requested_folder, match
            )
            return match.folder
        else:
            logger.info("No approved requests for folder %s", requested_folder)
            return None


class _ConnectToFolderPolicy(object):
    def ctf_policy(self, fingerprint: str) -> str:
        return "/etc/qubes-rpc/policy/ruddo.ConnectToFolder+%s" % fingerprint

    def grant_for(self, source: str, target: str, fingerprint: str) -> None:
        fn = self.ctf_policy(fingerprint)
        if os.path.isfile(fn):
            return
        logger.info("Creating %s", fn)
        with open(fn + ".tmp", "w") as f:
            f.write("%s %s allow" % (source, target))
        os.chmod(fn + ".tmp", 0o664)
        os.rename(fn + ".tmp", fn)

    def revoke_for(
        self, unused_source: str, unused_target: str, fingerprint: str
    ) -> None:
        fn = self.ctf_policy(fingerprint)
        try:
            os.unlink(fn)
            logger.info("Removing %s", fn)
        except FileNotFoundError:
            pass

    def apply_policy_changes_from(self, matrix: DecisionMatrix) -> None:
        tpl = "/etc/qubes-rpc/policy/ruddo.ConnectToFolder+%s"
        existing_policy_files = glob.glob(tpl % "*")
        for fingerprint, decision in matrix.items():
            if tpl % fingerprint in existing_policy_files:
                existing_policy_files.remove(tpl % fingerprint)
            action = {
                RESPONSE_ALLOW_ONETIME: self.grant_for,
                RESPONSE_ALLOW_ALWAYS: self.grant_for,
                RESPONSE_DENY_ONETIME: self.revoke_for,
                RESPONSE_DENY_ALWAYS: self.revoke_for,
            }[decision.response]
            action(decision.source, decision.target, fingerprint)
        for p in existing_policy_files:
            logger.info("Removing %s", p)
            os.unlink(p)


ConnectToFolderPolicy = _ConnectToFolderPolicy()
