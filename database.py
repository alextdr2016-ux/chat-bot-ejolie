import sqlite3
import os
import json
import uuid
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "chat_database.db")


class Database:
    """Handle all database operations for chatbot (analytics-safe, multi-tenant ready)"""

    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================
    # INIT DB
    # =========================
    def init_db(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # TENANTS
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain TEXT,
                    api_key TEXT UNIQUE NOT NULL,
                    plan TEXT DEFAULT 'free',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # CONVERSATIONS (tenant_id added but OPTIONAL)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT DEFAULT 'default',
                    session_id TEXT UNIQUE NOT NULL,
                    user_ip TEXT,
                    user_agent TEXT,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    total_messages INTEGER DEFAULT 0,
                    message_count_user INTEGER DEFAULT 0,
                    message_count_bot INTEGER DEFAULT 0,
                    on_topic_count INTEGER DEFAULT 0,
                    off_topic_count INTEGER DEFAULT 0,
                    conversation_duration_seconds INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    notes TEXT,
                    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # MESSAGES
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    sender TEXT NOT NULL,
                    message TEXT NOT NULL,
                    message_type TEXT DEFAULT 'text',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response_time_ms INTEGER,
                    status TEXT DEFAULT 'success',
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)

            # ANALYTICS CACHE
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    total_conversations INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    avg_messages_per_conversation REAL DEFAULT 0,
                    on_topic_percentage REAL DEFAULT 0,
                    off_topic_percentage REAL DEFAULT 0,
                    avg_response_time_ms INTEGER DEFAULT 0,
                    unique_sessions INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            conn.close()
            logger.info("✅ Database initialized (analytics compatible)")

        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
            raise

    # =========================
    # TENANTS
    # =========================
    def create_tenant(self, name, domain=None, plan="free"):
        tenant_id = str(uuid.uuid4())
        api_key = str(uuid.uuid4())

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tenants (id, name, domain, api_key, plan)
            VALUES (?, ?, ?, ?, ?)
        """, (tenant_id, name, domain, api_key, plan))
        conn.commit()
        conn.close()

        return {"tenant_id": tenant_id, "api_key": api_key}

    def get_tenant_by_api_key(self, api_key):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tenants WHERE api_key = ?", (api_key,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # =========================
    # CONVERSATIONS (BACKWARD SAFE)
    # =========================
    def save_conversation(
        self,
        session_id,
        user_message,
        bot_response,
        user_ip=None,
        user_agent=None,
        is_on_topic=True,
        tenant_id="default"
    ):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM conversations WHERE session_id = ?",
                (session_id,)
            )
            conversation = cursor.fetchone()

            if not conversation:
                cursor.execute("""
                    INSERT INTO conversations
                    (tenant_id, session_id, user_ip, user_agent, start_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (tenant_id, session_id, user_ip, user_agent, datetime.now()))
                conn.commit()
                conversation_id = cursor.lastrowid
            else:
                conversation_id = conversation["id"]

            cursor.execute("""
                INSERT INTO conversation_messages (conversation_id, sender, message)
                VALUES (?, 'user', ?)
            """, (conversation_id, user_message))

            cursor.execute("""
                INSERT INTO conversation_messages (conversation_id, sender, message)
                VALUES (?, 'bot', ?)
            """, (conversation_id, bot_response))

            cursor.execute("""
                UPDATE conversations SET
                    total_messages = total_messages + 2,
                    message_count_user = message_count_user + 1,
                    message_count_bot = message_count_bot + 1,
                    on_topic_count = on_topic_count + ?,
                    off_topic_count = off_topic_count + ?,
                    end_time = ?
                WHERE id = ?
            """, (
                1 if is_on_topic else 0,
                0 if is_on_topic else 1,
                datetime.now(),
                conversation_id
            ))

            conn.commit()
            conn.close()
            return conversation_id

        except Exception as e:
            logger.error(f"❌ Error saving conversation: {e}")
            return None

    # =========================
    # ANALYTICS (UNCHANGED API)
    # =========================
    def get_analytics(self, days=30):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_from = (datetime.now() - timedelta(days=days)).date()

            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT id) as total_conversations,
                    SUM(total_messages) as total_messages,
                    AVG(total_messages) as avg_messages_per_conversation,
                    SUM(on_topic_count) as total_on_topic,
                    SUM(off_topic_count) as total_off_topic,
                    COUNT(DISTINCT session_id) as unique_sessions
                FROM conversations
                WHERE DATE(start_time) >= ?
            """, (date_from,))

            result = dict(cursor.fetchone())

            total_topic = (result.get("total_on_topic") or 0) + \
                (result.get("total_off_topic") or 0)
            if total_topic > 0:
                result["on_topic_percentage"] = (
                    result["total_on_topic"] or 0) / total_topic * 100
                result["off_topic_percentage"] = (
                    result["total_off_topic"] or 0) / total_topic * 100

            else:
                result["on_topic_percentage"] = 0
                result["off_topic_percentage"] = 0

            conn.close()
            return result

        except Exception as e:
            logger.error(f"❌ Error fetching analytics: {e}")
            return {}


# Singleton
db = Database()
