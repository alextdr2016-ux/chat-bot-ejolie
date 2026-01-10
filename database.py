import sqlite3
import os
import json
import uuid
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "chat_database.db")


class Database:
    """Handle all database operations for chatbot (now multi-tenant ready)"""

    def __init__(self):
        """Initialize database connection"""
        self.db_path = DATABASE_PATH
        self.init_db()

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn

    # =========================
    # SCHEMA HELPERS (NEW)
    # =========================
    def _table_has_column(self, conn, table_name: str, column_name: str) -> bool:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        cols = [row["name"] for row in cursor.fetchall()]
        return column_name in cols

    def init_db(self):
        """Initialize database tables"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # =========================
            # TENANTS TABLE (NEW)
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
            # CONVERSATIONS TABLE
            # (MODIFIED: adds tenant_id)
            # =========================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
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

            # If DB existed before, ensure tenant_id column exists (safe migration)
            if not self._table_has_column(conn, "conversations", "tenant_id"):
                cursor.execute(
                    "ALTER TABLE conversations ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
                conn.commit()

            # Conversation messages table
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

            # Analytics table (cached stats)
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

            # Create indexes for faster queries
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_start_time ON conversations(start_time)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON conversation_messages(conversation_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON conversation_messages(timestamp)")

            conn.commit()
            conn.close()
            logger.info(
                "✅ Database initialized successfully (multi-tenant ready)")

        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
            raise

    # =========================
    # TENANTS (NEW)
    # =========================
    def create_tenant(self, name, domain=None, plan="free"):
        """Create a new SaaS tenant (store/client)"""
        try:
            tenant_id = str(uuid.uuid4())
            api_key = str(uuid.uuid4())
            created_at = datetime.utcnow().isoformat()

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tenants (id, name, domain, api_key, plan, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, name, domain, api_key, plan, created_at))
            conn.commit()
            conn.close()

            return {"tenant_id": tenant_id, "api_key": api_key}

        except Exception as e:
            logger.error(f"❌ Error creating tenant: {e}")
            return None

    def get_tenant_by_api_key(self, api_key):
        """Find tenant by api_key (used by widget/backend)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tenants WHERE api_key = ?", (api_key,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ Error fetching tenant: {e}")
            return None

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
        tenant_id="default",   # NEW: optional, keeps old behavior
    ):
        """Save conversation message to database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if conversation exists
            cursor.execute(
                "SELECT id FROM conversations WHERE session_id = ? AND tenant_id = ?",
                (session_id, tenant_id),
            )
            conversation = cursor.fetchone()

            if not conversation:
                # Create new conversation
                cursor.execute("""
                    INSERT INTO conversations
                    (tenant_id, session_id, user_ip, user_agent, start_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (tenant_id, session_id, user_ip, user_agent, datetime.now()))
                conn.commit()

                conversation_id = cursor.lastrowid
                logger.info(
                    f"🆕 New conversation created: {session_id} (tenant={tenant_id})")
            else:
                conversation_id = conversation["id"]

            # Save user message
            cursor.execute("""
                INSERT INTO conversation_messages
                (conversation_id, sender, message, message_type, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (conversation_id, "user", user_message, "text", datetime.now()))

            # Save bot response
            cursor.execute("""
                INSERT INTO conversation_messages
                (conversation_id, sender, message, message_type, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (conversation_id, "bot", bot_response, "text", datetime.now()))

            # Update conversation counts
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

            logger.info(
                f"💾 Conversation saved: {session_id} (tenant={tenant_id})")
            return conversation_id

        except Exception as e:
            logger.error(f"❌ Error saving conversation: {e}")
            return None

    def get_conversations(self, limit=100, offset=0, filters=None, tenant_id=None):
        """Get conversations with optional filters (tenant-aware)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM conversations WHERE 1=1"
            params = []

            # NEW: tenant filter (if provided)
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
            params_with_paging = params + [limit, offset]

            cursor.execute(query, params_with_paging)
            conversations = [dict(row) for row in cursor.fetchall()]

            # Total count (safe)
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
                if filters.get("keyword"):
                    count_query += """
                        AND id IN (
                            SELECT conversation_id FROM conversation_messages
                            WHERE message LIKE ?
                        )
                    """
                    count_params.append(f'%{filters["keyword"]}%')

            cursor.execute(count_query, count_params)
            total_count = cursor.fetchone()["count"]

            conn.close()
            return conversations, total_count

        except Exception as e:
            logger.error(f"❌ Error fetching conversations: {e}")
            return [], 0

    def get_conversation_messages(self, conversation_id):
        """Get all messages for a conversation"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))

            messages = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return messages

        except Exception as e:
            logger.error(f"❌ Error fetching messages: {e}")
            return []

    def get_analytics(self, days=30, tenant_id=None):
        """Get analytics for last N days (tenant-aware)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_from = (datetime.now() - timedelta(days=days)).date()

            query = """
                SELECT
                    COUNT(DISTINCT id) as total_conversations,
                    SUM(total_messages) as total_messages,
                    AVG(total_messages) as avg_messages_per_conversation,
                    SUM(on_topic_count) as total_on_topic,
                    SUM(off_topic_count) as total_off_topic,
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

            # Calculate percentages
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
        """Get daily statistics (tenant-aware)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_from = (datetime.now() - timedelta(days=days)).date()

            query = """
                SELECT
                    DATE(start_time) as date,
                    COUNT(*) as conversation_count,
                    SUM(total_messages) as message_count,
                    SUM(on_topic_count) as on_topic_count,
                    SUM(off_topic_count) as off_topic_count,
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
            stats = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return stats

        except Exception as e:
            logger.error(f"❌ Error fetching daily stats: {e}")
            return []

    def get_top_questions(self, limit=10, tenant_id=None):
        """Get most asked questions (tenant-aware)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # If tenant_id provided, restrict to conversations of that tenant
            if tenant_id:
                cursor.execute("""
                    SELECT
                        cm.message,
                        COUNT(*) as count
                    FROM conversation_messages cm
                    JOIN conversations c ON c.id = cm.conversation_id
                    WHERE cm.sender = 'user' AND c.tenant_id = ?
                    GROUP BY cm.message
                    ORDER BY count DESC
                    LIMIT ?
                """, (tenant_id, limit))
            else:
                cursor.execute("""
                    SELECT
                        message,
                        COUNT(*) as count
                    FROM conversation_messages
                    WHERE sender = 'user'
                    GROUP BY message
                    ORDER BY count DESC
                    LIMIT ?
                """, (limit,))

            questions = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return questions

        except Exception as e:
            logger.error(f"❌ Error fetching top questions: {e}")
            return []

    def delete_conversation(self, conversation_id):
        """Delete a conversation and its messages"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
            cursor.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,))

            conn.commit()
            conn.close()

            logger.info(f"🗑️ Conversation deleted: {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error deleting conversation: {e}")
            return False

    def export_conversations_csv(self, tenant_id=None):
        """Export conversations to CSV format (tenant-aware)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if tenant_id:
                cursor.execute("""
                    SELECT * FROM conversations
                    WHERE tenant_id = ?
                    ORDER BY start_time DESC
                """, (tenant_id,))
            else:
                cursor.execute(
                    "SELECT * FROM conversations ORDER BY start_time DESC")

            conversations = cursor.fetchall()

            csv_data = "ID,Tenant ID,Session ID,Start Time,End Time,Total Messages,On-Topic,Off-Topic,Status\n"
            for row in conversations:
                csv_data += (
                    f'{row["id"]},"{row["tenant_id"]}","{row["session_id"]}","{row["start_time"]}",'
                    f'"{row["end_time"]}",{row["total_messages"]},{row["on_topic_count"]},'
                    f'{row["off_topic_count"]},"{row["status"]}"\n'
                )

            conn.close()
            return csv_data

        except Exception as e:
            logger.error(f"❌ Error exporting CSV: {e}")
            return None

    def cleanup_old_conversations(self, days=90, tenant_id=None):
        """Delete conversations older than N days (tenant-aware)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_cutoff = (datetime.now() - timedelta(days=days)).date()

            if tenant_id:
                # Delete only for one tenant
                cursor.execute("""
                    DELETE FROM conversation_messages
                    WHERE conversation_id IN (
                        SELECT id FROM conversations
                        WHERE tenant_id = ? AND DATE(start_time) < ?
                    )
                """, (tenant_id, date_cutoff))
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE tenant_id = ? AND DATE(start_time) < ?
                """, (tenant_id, date_cutoff))
            else:
                # Delete for all tenants
                cursor.execute("""
                    DELETE FROM conversation_messages
                    WHERE conversation_id IN (
                        SELECT id FROM conversations
                        WHERE DATE(start_time) < ?
                    )
                """, (date_cutoff,))
                cursor.execute(
                    "DELETE FROM conversations WHERE DATE(start_time) < ?", (date_cutoff,))

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"🧹 Deleted {deleted_count} old conversations")
            return deleted_count

        except Exception as e:
            logger.error(f"❌ Error cleaning up conversations: {e}")
            return 0


# Initialize database
db = Database()
