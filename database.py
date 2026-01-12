import sqlite3
import os
import logging
import uuid
import csv
import io
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

# ✅ SET TIMEZONE TO ROMANIA
TZ = pytz.timezone('Europe/Bucharest')
TZ = pytz.timezone('Europe/London')        # London
TZ = pytz.timezone('Europe/Paris')         # Paris
TZ = pytz.timezone('America/New_York')     # NYC
TZ = pytz.timezone('Asia/Tokyo')           # Tokyo
TZ = pytz.timezone('Australia/Sydney')     # Sydney

DATABASE_PATH = os.getenv("DATABASE_PATH", "chat_database.db")


class Database:
    """
    Handle all database operations for chatbot
    analytics-safe, multi-tenant ready, magic-link auth ready
    Auto-syncs products from feed on startup if needed
    """

    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_db()
        # ✅ Auto-sync from feed on startup
        self.ensure_initial_sync()

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
            # USERS (PASSWORD LOGIN)
            # =========================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT,
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
            # SYNC LOG (for tracking feed syncs)
            # =========================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT DEFAULT 'default',
                    sync_type TEXT DEFAULT 'feed',
                    last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    products_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'success',
                    error_message TEXT,
                    FOREIGN KEY(tenant_id) REFERENCES tenants(id)
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
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_log_tenant_id ON sync_log(tenant_id)")

            conn.commit()
            conn.close()

            logger.info(
                "✅ Database initialized (analytics + saas + auth + sync compatible)")

        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
            raise

    # =========================
    # SYNC LOG METHODS
    # =========================
    def get_last_sync(self, tenant_id="default"):
        """Get last sync timestamp for tenant"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT last_sync, products_count FROM sync_log
                WHERE tenant_id = ? AND status = 'success'
                ORDER BY last_sync DESC
                LIMIT 1
            """, (tenant_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ Error get_last_sync: {e}")
            return None

    def log_sync(self, tenant_id="default", products_count=0, status="success", error=None):
        """Log a sync operation"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_log (tenant_id, last_sync, products_count, status, error_message)
                VALUES (?, ?, ?, ?, ?)
            """, (tenant_id, datetime.now(), products_count, status, error))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Error log_sync: {e}")
            return False

    def should_sync_from_feed(self, tenant_id="default", hours=6):
        """Check if we should sync from feed (last sync older than N hours)"""
        try:
            last_sync = self.get_last_sync(tenant_id)

            if not last_sync:
                logger.info(
                    f"📥 No previous sync found for {tenant_id} - should sync")
                return True

            last_sync_time = datetime.fromisoformat(last_sync['last_sync'])
            hours_since = (datetime.now() -
                           last_sync_time).total_seconds() / 3600

            if hours_since >= hours:
                logger.info(
                    f"📥 {hours_since:.1f}h since last sync - should sync")
                return True

            logger.info(f"✅ Sync done {hours_since:.1f}h ago - no sync needed")
            return False
        except Exception as e:
            logger.error(f"❌ Error should_sync_from_feed: {e}")
            return False

    def ensure_initial_sync(self):
        """Called on startup - syncs from feed if needed"""
        try:
            logger.info("🔍 Checking if feed sync is needed...")

            if self.should_sync_from_feed(tenant_id="default", hours=6):
                logger.info("⏳ Syncing from feed on startup...")

                try:
                    # Import here to avoid circular imports
                    from sync_feed import sync_products_from_feed

                    result = sync_products_from_feed()

                    if result.get("status") == "success":
                        products_count = result.get("products_count", 0)
                        self.log_sync(
                            tenant_id="default",
                            products_count=products_count,
                            status="success"
                        )
                        logger.info(
                            f"✅ Startup sync complete: {products_count} products loaded")
                        return True
                    else:
                        error_msg = result.get("message", "Unknown error")
                        self.log_sync(
                            tenant_id="default",
                            status="failed",
                            error=error_msg
                        )
                        logger.warning(f"⚠️ Startup sync failed: {error_msg}")
                        return False

                except ImportError:
                    logger.warning(
                        "⚠️ sync_feed module not found - skipping startup sync")
                    return False
                except Exception as e:
                    error_msg = str(e)
                    self.log_sync(
                        tenant_id="default",
                        status="failed",
                        error=error_msg
                    )
                    logger.error(f"❌ Startup sync error: {e}")
                    return False
            else:
                logger.info(
                    "✅ Feed sync not needed (recent sync already done)")
                return True

        except Exception as e:
            logger.error(f"❌ Error in ensure_initial_sync: {e}")
            return False

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
    # USERS + PASSWORD LOGIN
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

    def set_user_password(self, email, password_hash):
        """Set password hash for user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET password_hash = ?
                WHERE email = ?
            """, (password_hash, email.lower().strip()))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Error set_user_password: {e}")
            return False

    def verify_user_password(self, email, password_hash):
        """Verify user password"""
        try:
            user = self.get_user_by_email(email)
            if not user:
                return None

            if user.get('password_hash') == password_hash:
                return user

            return None
        except Exception as e:
            logger.error(f"❌ Error verify_user_password: {e}")
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
    # ANALYTICS METHODS
    # =========================
    def get_conversations(self, limit=50, offset=0, filters=None, tenant_id=None):
        """Get conversations with optional filters"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM conversations WHERE 1=1"
            params = []

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            if filters:
                if filters.get('date_from'):
                    query += " AND DATE(start_time) >= ?"
                    params.append(filters['date_from'])

                if filters.get('date_to'):
                    query += " AND DATE(start_time) <= ?"
                    params.append(filters['date_to'])

                if filters.get('status'):
                    query += " AND status = ?"
                    params.append(filters['status'])

                if filters.get('keyword'):
                    keyword = filters['keyword']
                    query += f" AND id IN (SELECT conversation_id FROM conversation_messages WHERE message LIKE ?)"
                    params.append(f"%{keyword}%")

            # Count total
            count_query = f"SELECT COUNT(*) FROM conversations WHERE 1=1"
            count_params = []
            if tenant_id:
                count_query += " AND tenant_id = ?"
                count_params.append(tenant_id)
            if filters:
                if filters.get('date_from'):
                    count_query += " AND DATE(start_time) >= ?"
                    count_params.append(filters['date_from'])
                if filters.get('date_to'):
                    count_query += " AND DATE(start_time) <= ?"
                    count_params.append(filters['date_to'])
                if filters.get('status'):
                    count_query += " AND status = ?"
                    count_params.append(filters['status'])

            cursor.execute(count_query, count_params)
            total = cursor.fetchone()[0]

            # Get paginated results
            query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            conversations = [dict(row) for row in rows]
            return conversations, total

        except Exception as e:
            logger.error(f"❌ Error get_conversations: {e}")
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

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"❌ Error get_conversation_messages: {e}")
            return []

    def get_analytics(self, days=30, tenant_id=None):
        """Get overall analytics stats"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    COUNT(DISTINCT id) as total_conversations,
                    SUM(total_messages) as total_messages,
                    SUM(on_topic_count) as on_topic_count,
                    SUM(off_topic_count) as off_topic_count,
                    COUNT(DISTINCT session_id) as unique_sessions
                FROM conversations
                WHERE start_time >= datetime('now', '-' || ? || ' days')
            """
            params = [days]

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.close()

            if row:
                total_convs = row[0] or 0
                total_msgs = row[1] or 0
                on_topic = row[2] or 0
                off_topic = row[3] or 0
                unique = row[4] or 0

                on_topic_pct = (on_topic / (on_topic + off_topic) * 100) if (
                    on_topic + off_topic) > 0 else 0

                return {
                    "total_conversations": total_convs,
                    "total_messages": total_msgs,
                    "on_topic_percentage": round(on_topic_pct, 2),
                    "off_topic_percentage": round(100 - on_topic_pct, 2),
                    "unique_sessions": unique
                }

            return {
                "total_conversations": 0,
                "total_messages": 0,
                "on_topic_percentage": 0,
                "off_topic_percentage": 0,
                "unique_sessions": 0
            }

        except Exception as e:
            logger.error(f"❌ Error get_analytics: {e}")
            return {}

    def get_daily_stats(self, days=30, tenant_id=None):
        """Get daily statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    DATE(start_time) as date,
                    COUNT(id) as conversations,
                    SUM(total_messages) as messages,
                    SUM(on_topic_count) as on_topic
                FROM conversations
                WHERE start_time >= datetime('now', '-' || ? || ' days')
            """
            params = [days]

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            query += " GROUP BY DATE(start_time) ORDER BY date DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"❌ Error get_daily_stats: {e}")
            return []

    def get_top_questions(self, limit=10, tenant_id=None):
        """Get most asked questions"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = """
                SELECT message, COUNT(*) as count
                FROM conversation_messages
                WHERE sender = 'user'
                  AND conversation_id IN (
                    SELECT id FROM conversations
            """
            params = []

            if tenant_id:
                query += " WHERE tenant_id = ?"
                params.append(tenant_id)

            query += """
                  )
                GROUP BY message
                ORDER BY count DESC
                LIMIT ?
            """
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"❌ Error get_top_questions: {e}")
            return []

    def delete_conversation(self, conversation_id):
        """Delete conversation and all its messages"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM conversation_messages
                WHERE conversation_id = ?
            """, (conversation_id,))

            cursor.execute("""
                DELETE FROM conversations
                WHERE id = ?
            """, (conversation_id,))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error delete_conversation: {e}")
            return False

    def export_conversations_csv(self, tenant_id=None):
        """Export conversations to CSV"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM conversations WHERE 1=1"
            params = []

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            query += " ORDER BY start_time DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                return None

            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Headers
            headers = [description[0]
                       for description in cursor.description]
            writer.writerow(headers)

            # Data
            for row in rows:
                writer.writerow(row)

            conn.close()

            csv_str = output.getvalue()
            return csv_str.encode('utf-8')

        except Exception as e:
            logger.error(f"❌ Error export_conversations_csv: {e}")
            return None

    def cleanup_old_conversations(self, days=90, tenant_id=None):
        """Delete conversations older than N days"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = """
                DELETE FROM conversations
                WHERE start_time < datetime('now', '-' || ? || ' days')
            """
            params = [days]

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            cursor.execute(query, params)
            deleted = cursor.rowcount

            conn.commit()
            conn.close()

            return deleted

        except Exception as e:
            logger.error(f"❌ Error cleanup_old_conversations: {e}")
            return 0


# Singleton
db = Database()
