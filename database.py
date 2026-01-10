import sqlite3
import os
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "chat_database.db")


class Database:
    """Handle all database operations for chatbot (analytics-safe, multi-tenant ready, auth-ready)"""

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

            # USERS (MAGIC LINK LOGIN)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    role TEXT NOT NULL DEFAULT 'client',   -- 'admin' or 'client'
                    tenant_id TEXT,
                    login_token TEXT,
                    token_expiry TIMESTAMP,
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

            # ANALYTICS CACHE (optional legacy)
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

            # INDEXES (helps a lot)
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
    # USERS + MAGIC LINK TOKENS
    # =========================
    def get_user_by_email(self, email: str):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ Error get_user_by_email: {e}")
            return None

    def create_user_if_missing(self, email: str, role: str = "client", tenant_id: str = None):
        existing = self.get_user_by_email(email)
        if existing:
            return existing

        try:
            user_id = str(uuid.uuid4())
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, email, role, tenant_id)
                VALUES (?, ?, ?, ?)
            """, (user_id, email, role, tenant_id))
            conn.commit()
            conn.close()
            return self.get_user_by_email(email)
        except Exception as e:
            logger.error(f"❌ Error create_user_if_missing: {e}")
            return None

    def create_login_token(self, email: str, minutes: int = 15):
        try:
            token = str(uuid.uuid4())
            expiry = datetime.utcnow() + timedelta(minutes=minutes)

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET login_token = ?, token_expiry = ?
                WHERE email = ?
            """, (token, expiry.isoformat(), email))
            conn.commit()
            conn.close()

            return token
        except Exception as e:
            logger.error(f"❌ Error create_login_token: {e}")
            return None

    def get_user_by_token(self, token: str):
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

    def clear_login_token(self, user_id: str):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET login_token = NULL, token_expiry = NULL
                WHERE id = ?
            """, (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Error clear_login_token: {e}")
            return False

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

    def get_conversation_messages(self, conversation_id: int):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"❌ Error fetching messages: {e}")
            return []

    # =========================
    # LIST CONVERSATIONS (analytics)
    # tenant_id OPTIONAL
    # =========================
    def get_conversations(self, limit=100, offset=0, filters=None, tenant_id=None):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM conversations WHERE 1=1"
            params = []

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            if filters:
                if filters.get("date_from"):
                    query += " AND DATE(start_time) >= ?"
                    params.append(filters["date_from"])

                if filters.get("date_to"):
                    query += " AND DATE(start_time) <= ?"
                    params.append(filters["date_to"])

                if filters.get("status"):
                    query += " AND status = ?"
                    params.append(filters["status"])

                if filters.get("keyword"):
                    query += """
                        AND id IN (
                            SELECT conversation_id FROM conversation_messages
                            WHERE message LIKE ?
                        )
                    """
                    params.append(f'%{filters["keyword"]}%')

            query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            conversations = [dict(row) for row in cursor.fetchall()]

            # total count (same filters)
            count_query = "SELECT COUNT(*) as count FROM conversations WHERE 1=1"
            count_params = []

            if tenant_id:
                count_query += " AND tenant_id = ?"
                count_params.append(tenant_id)

            if filters:
                if filters.get("date_from"):
                    count_query += " AND DATE(start_time) >= ?"
                    count_params.append(filters["date_from"])
                if filters.get("date_to"):
                    count_query += " AND DATE(start_time) <= ?"
                    count_params.append(filters["date_to"])
                if filters.get("status"):
                    count_query += " AND status = ?"
                    count_params.append(filters["status"])

            cursor.execute(count_query, count_params)
            total_count = cursor.fetchone()["count"]

            conn.close()
            return conversations, total_count

        except Exception as e:
            logger.error(f"❌ Error fetching conversations: {e}")
            return [], 0

    # =========================
    # ANALYTICS STATS
    # tenant_id OPTIONAL
    # =========================
    def get_analytics(self, days=30, tenant_id=None):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_from = (datetime.now() - timedelta(days=days)).date()

            query = """
                SELECT
                    COUNT(DISTINCT id) as total_conversations,
                    COALESCE(SUM(total_messages), 0) as total_messages,
                    COALESCE(AVG(total_messages), 0) as avg_messages_per_conversation,
                    COALESCE(SUM(on_topic_count), 0) as total_on_topic,
                    COALESCE(SUM(off_topic_count), 0) as total_off_topic,
                    COUNT(DISTINCT session_id) as unique_sessions
                FROM conversations
                WHERE DATE(start_time) >= ?
            """
            params = [date_from]

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            cursor.execute(query, params)
            result = dict(cursor.fetchone())

            total_topic = (result.get("total_on_topic") or 0) + \
                (result.get("total_off_topic") or 0)
            if total_topic > 0:
                result["on_topic_percentage"] = (result.get(
                    "total_on_topic") or 0) / total_topic * 100
                result["off_topic_percentage"] = (result.get(
                    "total_off_topic") or 0) / total_topic * 100
            else:
                result["on_topic_percentage"] = 0
                result["off_topic_percentage"] = 0

            conn.close()
            return result

        except Exception as e:
            logger.error(f"❌ Error fetching analytics: {e}")
            return {}

    def get_daily_stats(self, days=30, tenant_id=None):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_from = (datetime.now() - timedelta(days=days)).date()

            query = """
                SELECT
                    DATE(start_time) as date,
                    COUNT(*) as conversation_count,
                    COALESCE(SUM(total_messages), 0) as message_count,
                    COALESCE(SUM(on_topic_count), 0) as on_topic_count,
                    COALESCE(SUM(off_topic_count), 0) as off_topic_count,
                    COUNT(DISTINCT session_id) as unique_sessions
                FROM conversations
                WHERE DATE(start_time) >= ?
            """
            params = [date_from]

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            query += " GROUP BY DATE(start_time) ORDER BY date DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]

        except Exception as e:
            logger.error(f"❌ Error fetching daily stats: {e}")
            return []

    def get_top_questions(self, limit=10, tenant_id=None):
        """
        Top user messages.
        If tenant_id is provided, restrict to that tenant.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = """
                SELECT cm.message, COUNT(*) as count
                FROM conversation_messages cm
                JOIN conversations c ON c.id = cm.conversation_id
                WHERE cm.sender = 'user'
            """
            params = []

            if tenant_id:
                query += " AND c.tenant_id = ?"
                params.append(tenant_id)

            query += """
                GROUP BY cm.message
                ORDER BY count DESC
                LIMIT ?
            """
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]

        except Exception as e:
            logger.error(f"❌ Error fetching top questions: {e}")
            return []

    # =========================
    # EXPORT CSV (analytics)
    # tenant_id OPTIONAL
    # =========================
    def export_conversations_csv(self, tenant_id=None):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM conversations"
            params = []
            if tenant_id:
                query += " WHERE tenant_id = ?"
                params.append(tenant_id)

            query += " ORDER BY start_time DESC"

            cursor.execute(query, params)
            conversations = cursor.fetchall()

            csv_data = "ID,Tenant ID,Session ID,Start Time,End Time,Total Messages,On-Topic,Off-Topic,Status\n"
            for row in conversations:
                csv_data += (
                    f'{row["id"]},"{row["tenant_id"]}","{row["session_id"]}",'
                    f'"{row["start_time"]}","{row["end_time"]}",{row["total_messages"]},'
                    f'{row["on_topic_count"]},{row["off_topic_count"]},"{row["status"]}"\n'
                )

            conn.close()
            return csv_data

        except Exception as e:
            logger.error(f"❌ Error exporting CSV: {e}")
            return None

    # =========================
    # DELETE + CLEANUP
    # =========================
    def delete_conversation(self, conversation_id: int):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
            cursor.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error deleting conversation: {e}")
            return False

    def cleanup_old_conversations(self, days=90, tenant_id=None):
        """
        Delete conversations older than N days.
        If tenant_id is provided, delete only for that tenant.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_cutoff = (datetime.now() - timedelta(days=days)).date()

            if tenant_id:
                cursor.execute("""
                    SELECT id FROM conversations
                    WHERE DATE(start_time) < ? AND tenant_id = ?
                """, (date_cutoff, tenant_id))
            else:
                cursor.execute("""
                    SELECT id FROM conversations
                    WHERE DATE(start_time) < ?
                """, (date_cutoff,))

            ids = [r["id"] for r in cursor.fetchall()]

            if not ids:
                conn.close()
                return 0

            # delete messages
            cursor.executemany("DELETE FROM conversation_messages WHERE conversation_id = ?", [
                               (i,) for i in ids])
            # delete conversations
            cursor.executemany("DELETE FROM conversations WHERE id = ?", [
                               (i,) for i in ids])

            conn.commit()
            conn.close()
            return len(ids)

        except Exception as e:
            logger.error(f"❌ Error cleaning up conversations: {e}")
            return 0


# Singleton
db = Database()
