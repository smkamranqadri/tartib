"""Generate a VAPID key pair for push reminders.

    uv run python -m tartib.vapid        # prints the two lines to paste into .env

The keys are base64url strings rather than PEM files so they fit in the environment, which
is where every other secret in Tartib already lives.
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid02


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def generate() -> tuple[str, str]:
    """Returns (public, private). The public one is what the browser subscribes with."""
    vapid = Vapid02()
    vapid.generate_keys()
    public = b64(
        vapid.public_key.public_bytes(encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)
    )
    private = b64(vapid.private_key.private_numbers().private_value.to_bytes(32, "big"))
    return public, private


def main() -> None:
    public, private = generate()
    print("TARTIB_VAPID_PUBLIC=" + public)
    print("TARTIB_VAPID_PRIVATE=" + private)
    print("TARTIB_VAPID_EMAIL=mailto:you@example.com")


if __name__ == "__main__":
    main()
