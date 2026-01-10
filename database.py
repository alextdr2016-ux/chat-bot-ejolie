import sqlite3
import os
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "chat_database.db")


class Database:
    """
    Handle all database operations for chatbot
    analytics-safe, multi-tenant ready, magic-link auth ready
    """

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

            # =========================
            # TENANTS
            # =========================
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

            # =========================
            # USERS (MAGIC LINK LOGIN)
            # =========================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    role TEXT NOT NULL DEFAULT 'client',
                    tenant_id TEXT,
                    login_token TEXT,
                    token_expiry TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # =========================
            # CONVERSATIONS
            # =========================
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # =========================
            # CONVERSATION MESSAGES
            # =========================
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
                    FOREIGN KEY(conversation_id)
                        REFERENCES conversations(id)
                        ON DELETE CASCADE
                )
            """)

            # =========================
            # ANALYTICS CACHE
            # =========================
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

            # =========================
            # INDEXES
            # =========================
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_start_time ON conversations(start_time)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_tenant_id ON conversations(tenant_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON conversation_messages(conversation_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON conversation_messages(timestamp)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_token ON users(login_token)")

            conn.commit()
            conn.close()

            logger.info(
                "✅ Database initialized (analytics + saas + auth compatible)")

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
    # USERS + MAGIC LINK
    # =========================
    def get_user_by_email(self, email):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ Error get_user_by_email: {e}")
            return None

    def create_user_if_missing(self, email, role="client", tenant_id=None):
        user = self.get_user_by_email(email)
        if user:
            return user

        try:
            user_id = str(uuid.uuid4())
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, email, role, tenant_id)
                VALUES (?, ?, ?, ?)
            """, (user_id, email.lower().strip(), role, tenant_id))
            conn.commit()
            conn.close()
            return self.get_user_by_email(email)
        except Exception as e:
            logger.error(f"❌ Error create_user_if_missing: {e}")
            return None

    def create_login_token(self, email, minutes=15):
        try:
            token = str(uuid.uuid4())
            expiry = datetime.utcnow() + timedelta(minutes=minutes)

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET login_token = ?, token_expiry = ?
                WHERE email = ?
            """, (token, expiry.isoformat(), email.lower().strip()))
            conn.commit()
            conn.close()
            return token
        except Exception as e:
            logger.error(f"❌ Error create_login_token: {e}")
            return None

    def get_user_by_token(self, token):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users
                WHERE login_token = ?
                  AND token_expiry IS NOT NULL
                  AND token_expiry > ?
            """, (token, datetime.utcnow().isoformat()))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ Error get_user_by_token: {e}")
            return None

    def clear_login_token(self, user_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET login_token = NULL,
                    token_expiry = NULL
                WHERE id = ?
            """, (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Error clear_login_token: {e}")
            return False

    # =========================
    # CONVERSATIONS
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
                "SELECT id FROM conversations WHERE session_id = ?", (session_id,))
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
    # ANALYTICS + EXPORT + CLEANUP
    # (exactly as before, unchanged)
    # =========================
    # ... TOT CE AI AVUT MAI JOS RĂMÂNE IDENTIC ...


# Singleton
db = Database()
