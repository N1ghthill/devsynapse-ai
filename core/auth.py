"""
Authentication service backed by the memory database.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import jwt

from config.settings import get_settings
from core.memory import MemorySystem


class AuthService:
    """Handle user lifecycle and JWT tokens."""

    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
        self.settings = get_settings()

    def hash_password(self, password: str) -> str:
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return f"{salt.hex()}:{key.hex()}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        salt_hex, key_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        computed_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return hmac.compare_digest(expected_key, computed_key)

    def ensure_default_users(self):
        defaults = [
            (
                self.settings.default_admin_username,
                self.settings.default_admin_password,
                "admin",
            ),
        ]

        default_user = self.settings.default_user_username
        if default_user:
            defaults.append(
                (
                    default_user,
                    self.settings.default_user_password or default_user,
                    "user",
                )
            )

        for username, password, role in defaults:
            existing = self.memory.get_user(username)
            if existing is None:
                self.memory.upsert_user(
                    username=username,
                    password_hash=self.hash_password(password),
                    role=role,
                )

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        user = self.memory.get_user(username)
        if user is None or not user["is_active"]:
            return None

        if not self.verify_password(password, user["password_hash"]):
            return None

        self.memory.touch_user_login(username)
        return {
            "username": user["username"],
            "role": user["role"],
        }

    def create_access_token(self, user: Dict) -> str:
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.settings.access_token_expire_minutes
        )
        payload = {
            "sub": user["username"],
            "role": user["role"],
            "exp": expires_at,
        }
        return jwt.encode(
            payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )

    def verify_access_token(self, token: str) -> Optional[Dict]:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
        except jwt.PyJWTError:
            return None

        username = payload.get("sub")
        if not username:
            return None

        user = self.memory.get_user(username)
        if user is None or not user["is_active"]:
            return None

        return {
            "username": user["username"],
            "role": user["role"],
        }
