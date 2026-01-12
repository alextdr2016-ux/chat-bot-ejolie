#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database migration script to add password_hash column
"""

import sqlite3
import os

DATABASE_PATH = os.getenv("DATABASE_PATH", "chat_database.db")


def migrate_database():
    """Add password_hash column to users table"""

    print("=" * 60)
    print("Database Migration Script")
    print("=" * 60)
    print()

    if not os.path.exists(DATABASE_PATH):
        print(f"[INFO] Database not found at {DATABASE_PATH}")
        print("[INFO] No migration needed - will be created with correct schema")
        return True

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Check if password_hash column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'password_hash' in columns:
            print("[INFO] Column 'password_hash' already exists")
            print("[SUCCESS] No migration needed")
            conn.close()
            return True

        # Add password_hash column
        print("[INFO] Adding 'password_hash' column to users table...")
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN password_hash TEXT
        """)

        conn.commit()
        conn.close()

        print("[SUCCESS] Migration complete!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    try:
        success = migrate_database()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
