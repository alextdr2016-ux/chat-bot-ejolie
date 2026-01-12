#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick script to create admin user with password
Usage: python create_admin.py <email> <password>
Example: python create_admin.py admin@ejolie.ro MySecurePassword123
"""

import sys
from werkzeug.security import generate_password_hash
from database import db


def create_admin(email, password):
    """Create admin user with password"""

    email = email.strip().lower()

    if not email or "@" not in email:
        print(f"[ERROR] Invalid email: {email}")
        return False

    if len(password) < 6:
        print("[ERROR] Password must be at least 6 characters")
        return False

    # Create or get user
    user = db.get_user_by_email(email)

    if not user:
        print(f"[INFO] Creating new admin user: {email}")
        user = db.create_user_if_missing(email=email, role="admin")

        if not user:
            print("[ERROR] Failed to create user")
            return False
    else:
        print(f"[INFO] Updating existing user: {email}")

    # Hash password
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    # Set password
    success = db.set_user_password(email, password_hash)

    if success:
        print()
        print("=" * 60)
        print("[SUCCESS] Admin user configured!")
        print(f"   Email: {email}")
        print(f"   Role: {user.get('role', 'admin')}")
        print("=" * 60)
        print()
        print("Login at: /login")
        return True
    else:
        print("[ERROR] Failed to set password")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python create_admin.py <email> <password>")
        print("Example: python create_admin.py admin@ejolie.ro MyPassword123")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]

    try:
        success = create_admin(email, password)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
