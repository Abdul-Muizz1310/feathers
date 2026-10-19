"""Mint contract-v2 platform tokens for driving a generated service over HTTP.

The e2e and Postgres tiers boot the generated service as a separate process, so they
hand it the public half of a throwaway Ed25519 key through ``BASTION_SIGNING_KEY_PUBLIC``
and sign each request's token with the private half — exactly what bastion does.
"""

from __future__ import annotations

import base64
import time
import uuid
from dataclasses import dataclass, field

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@dataclass(frozen=True)
class BastionKey:
    """A throwaway stand-in for bastion's signing key."""

    private: Ed25519PrivateKey = field(default_factory=Ed25519PrivateKey.generate)

    @property
    def public_b64(self) -> str:
        """The public half as base64 SPKI DER (the ``BASTION_SIGNING_KEY_PUBLIC`` format)."""
        der = self.private.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(der).decode()

    def token(self, *, aud: str, role: str = "admin", sub: str = "v_e2etester") -> str:
        now = int(time.time())
        claims = {
            "iss": "bastion",
            "aud": aud,
            "service": aud,
            "sub": sub,
            "role": role,
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(claims, self.private, algorithm="EdDSA")

    def headers(self, *, aud: str, role: str = "admin") -> dict[str, str]:
        return {"X-Platform-Token": self.token(aud=aud, role=role)}
