"""Public-tree hygiene: tracked files must not contain host paths, client names, or live-looking secrets.

Needles are built at runtime so this file does not itself contain the strings it forbids.
"""
import os
import subprocess
import unittest

from tests.helpers import ROOT


def _needles():
    return {
        "personal-home": "/home/" + "joao" + "pedro",
        "personal-domain": "joao" + "pedro" + "coelho",
        "personal-email-local": "cada" + "stro@",
        "client-surname": "duar" + "tes",
        "client-product": "Legal" + "OS",
        "client-repo": "legal" + "os-essencial",
        "host-areas": "/srv/" + "rato" + "eira",
        "host-opt": "/opt/" + "rato" + "eira",
        "host-lib": "/usr/local/lib/" + "rato" + "eira",
        "host-socket": "/run/" + "rato" + "eira-agentes",
        "vault-item": "op://" + "rabbit" + "os/",
        "codex-account-id": "7eb7" + "fd750d",
        "private-canvas": "cursor.com/canvas/" + "store-",
        "key-helper-bin": "rato" + "eira-chave",
    }


def _tracked():
    listed = subprocess.run(
        ["git", "-C", ROOT, "ls-files", "-z"],
        capture_output=True, text=True, timeout=60,
    )
    return [rel for rel in listed.stdout.split("\0") if rel]


class PublicTree(unittest.TestCase):
    def test_tracked_files_omit_host_and_client_markers(self):
        skip = {"tests/test_public_hygiene.py"}
        needles = _needles()
        hits = []
        for rel in _tracked():
            if rel in skip:
                continue
            path = os.path.join(ROOT, rel)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
            except (OSError, UnicodeDecodeError):
                continue
            for kind, needle in needles.items():
                if needle in text:
                    hits.append("%s:%s" % (kind, rel))
        self.assertEqual(hits, [], "public tree still contains sensitive markers: %s" % hits)
