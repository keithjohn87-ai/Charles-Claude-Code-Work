#!/usr/bin/env python3
"""Generate a PBKDF2 password hash for use in CONTRPRO_BETA_USERS env var.

Usage:
    python3 scripts/contrpro_hash_password.py <password>
    python3 scripts/contrpro_hash_password.py            # prompts (no echo)

The output is a single line in the format:
    saltHex$iterations$hashHex

To add a new beta user, append to .env:
    CONTRPRO_BETA_USERS=existing@user.com:hash1,new@user.com:<output>

Then restart the webhook server.

The format matches what webhook_server.py:_verify_password() expects.
"""
from __future__ import annotations

import getpass
import hashlib
import secrets
import sys


def hash_password(password: str, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{salt.hex()}${iterations}${h.hex()}"


def main() -> int:
    if len(sys.argv) > 2:
        print(f"Usage: {sys.argv[0]} [<password>]", file=sys.stderr)
        return 2

    if len(sys.argv) == 2:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm:  ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1

    if len(password) < 8:
        print("Warning: password is shorter than 8 characters.", file=sys.stderr)

    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
