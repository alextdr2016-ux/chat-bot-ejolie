#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to set admin password for the chatbot application.
Usage: python set_admin_password.py
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')

from werkzeug.security import generate_password_hash
from database import db


def set_admin_password():
    """Set password for admin user"""

    print("=" * 60)
    print("Set Admin Password")
    print("=" * 60)
    print()

    # Get email
    email = input("Enter admin email: ").strip().lower()

    if not email or "@" not in email:
        print("[ERROR] Invalid email address")
        return False

    # Get password
    password = input("Enter password (min 6 characters): ").strip()

    if len(password) < 6:
        print("[ERROR] Password must be at least 6 characters")
        return False

    # Confirm password
    password_confirm = input("Confirm password: ").strip()

    if password != password_confirm:
        print("[ERROR] Passwords do not match")
        return False

    # Create or get user
    user = db.get_user_by_email(email)

    if not user:
        print(f"[INFO] Creating new admin user: {email}")
        user = db.create_user_if_missing(email=email, role="admin")

        if not user:
            print("[ERROR] Failed to create user")
            return False

    # Hash password
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    # Set password
    success = db.set_user_password(email, password_hash)

    if success:
        print()
        print("=" * 60)
        print("[SUCCESS] Password set successfully!")
        print(f"   Email: {email}")
        print(f"   Role: {user.get('role', 'admin')}")
        print("=" * 60)
        print()
        print("You can now login at: /login")
        return True
    else:
        print("[ERROR] Failed to set password")
        return False


if __name__ == "__main__":
    try:
        set_admin_password()
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        sys.exit(1)
