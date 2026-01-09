import sqlite3
import os
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv('DATABASE_PATH', 'chat_database.db')


class Database:
    """Handle all database operations for chatbot"""

    def __init__(self):
        """Initialize database connection"""
        self.db_path = DATABASE_PATH
        self.init_db()

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn

    def init_db(self):
        """Initialize database tables"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Conversations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            ''')

            # Conversation messages table
            cursor.execute('''
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
            ''')

            # Analytics table (cached stats)
            cursor.execute('''
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
            ''')

            # Create indexes for faster queries
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_conversations_start_time ON conversations(start_time)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON conversation_messages(conversation_id)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON conversation_messages(timestamp)')

            conn.commit()
            conn.close()
            logger.info("✅ Database initialized successfully")

        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
            raise

    def save_conversation(self, session_id, user_message, bot_response, user_ip=None, user_agent=None, is_on_topic=True):
        """Save conversation message to database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if conversation exists
            cursor.execute(
                'SELECT id FROM conversations WHERE session_id = ?', (session_id,))
            conversation = cursor.fetchone()

            if not conversation:
                # Create new conversation
                cursor.execute('''
                    INSERT INTO conversations 
                    (session_id, user_ip, user_agent, start_time) 
                    VALUES (?, ?, ?, ?)
                ''', (session_id, user_ip, user_agent, datetime.now()))
                conn.commit()

                conversation_id = cursor.lastrowid
                logger.info(f"🆕 New conversation created: {session_id}")
            else:
                conversation_id = conversation['id']

            # Save user message
            cursor.execute('''
                INSERT INTO conversation_messages 
                (conversation_id, sender, message, message_type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (conversation_id, 'user', user_message, 'text', datetime.now()))

            # Save bot response
            cursor.execute('''
                INSERT INTO conversation_messages 
                (conversation_id, sender, message, message_type, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (conversation_id, 'bot', bot_response, 'text', datetime.now()))

            # Update conversation counts
            cursor.execute('''
                UPDATE conversations SET 
                total_messages = total_messages + 2,
                message_count_user = message_count_user + 1,
                message_count_bot = message_count_bot + 1,
                on_topic_count = on_topic_count + ?,
                off_topic_count = off_topic_count + ?,
                end_time = ?
                WHERE id = ?
            ''', (1 if is_on_topic else 0, 0 if is_on_topic else 1, datetime.now(), conversation_id))

            conn.commit()
            conn.close()

            logger.info(f"💾 Conversation saved: {session_id}")
            return conversation_id

        except Exception as e:
            logger.error(f"❌ Error saving conversation: {e}")
            return None

    def get_conversations(self, limit=100, offset=0, filters=None):
        """Get conversations with optional filters"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = 'SELECT * FROM conversations WHERE 1=1'
            params = []

            if filters:
                if filters.get('date_from'):
                    query += ' AND DATE(start_time) >= ?'
                    params.append(filters['date_from'])

                if filters.get('date_to'):
                    query += ' AND DATE(start_time) <= ?'
                    params.append(filters['date_to'])

                if filters.get('status'):
                    query += ' AND status = ?'
                    params.append(filters['status'])

                if filters.get('keyword'):
                    query += ''' AND (
                        id IN (
                            SELECT conversation_id FROM conversation_messages 
                            WHERE message LIKE ?
                        )
                    )'''
                    params.append(f'%{filters["keyword"]}%')

            query += ' ORDER BY start_time DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            cursor.execute(query, params)
            conversations = [dict(row) for row in cursor.fetchall()]

            # Get message count
            cursor.execute('SELECT COUNT(*) as count FROM conversations WHERE 1=1' +
                           ('' if not filters else ' AND ' + ' AND '.join([
                               f"DATE(start_time) >= '{filters['date_from']}'" if filters.get(
                                   'date_from') else '',
                               f"DATE(start_time) <= '{filters['date_to']}'" if filters.get(
                                   'date_to') else '',
                               f"status = '{filters['status']}'" if filters.get(
                                   'status') else ''
                           ]).replace('  AND ', ' AND ').lstrip('AND')))
            total_count = cursor.fetchone()['count']

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

            cursor.execute('''
                SELECT * FROM conversation_messages 
                WHERE conversation_id = ? 
                ORDER BY timestamp ASC
            ''', (conversation_id,))

            messages = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return messages

        except Exception as e:
            logger.error(f"❌ Error fetching messages: {e}")
            return []

    def get_analytics(self, days=30):
        """Get analytics for last N days"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_from = (datetime.now() - timedelta(days=days)).date()

            cursor.execute('''
                SELECT 
                    COUNT(DISTINCT id) as total_conversations,
                    SUM(total_messages) as total_messages,
                    AVG(total_messages) as avg_messages_per_conversation,
                    SUM(on_topic_count) as total_on_topic,
                    SUM(off_topic_count) as total_off_topic,
                    COUNT(DISTINCT session_id) as unique_sessions
                FROM conversations
                WHERE DATE(start_time) >= ?
            ''', (date_from,))

            result = dict(cursor.fetchone())

            # Calculate percentages
            total_topic = (result.get('total_on_topic') or 0) + \
                (result.get('total_off_topic') or 0)
            if total_topic > 0:
                result['on_topic_percentage'] = (result.get(
                    'total_on_topic') or 0) / total_topic * 100
                result['off_topic_percentage'] = (result.get(
                    'total_off_topic') or 0) / total_topic * 100
            else:
                result['on_topic_percentage'] = 0
                result['off_topic_percentage'] = 0

            conn.close()
            return result

        except Exception as e:
            logger.error(f"❌ Error fetching analytics: {e}")
            return {}

    def get_daily_stats(self, days=30):
        """Get daily statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_from = (datetime.now() - timedelta(days=days)).date()

            cursor.execute('''
                SELECT 
                    DATE(start_time) as date,
                    COUNT(*) as conversation_count,
                    SUM(total_messages) as message_count,
                    SUM(on_topic_count) as on_topic_count,
                    SUM(off_topic_count) as off_topic_count,
                    COUNT(DISTINCT session_id) as unique_sessions
                FROM conversations
                WHERE DATE(start_time) >= ?
                GROUP BY DATE(start_time)
                ORDER BY date DESC
            ''', (date_from,))

            stats = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return stats

        except Exception as e:
            logger.error(f"❌ Error fetching daily stats: {e}")
            return []

    def get_top_questions(self, limit=10):
        """Get most asked questions"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT 
                    message,
                    COUNT(*) as count
                FROM conversation_messages
                WHERE sender = 'user'
                GROUP BY message
                ORDER BY count DESC
                LIMIT ?
            ''', (limit,))

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
                'DELETE FROM conversation_messages WHERE conversation_id = ?', (conversation_id,))
            cursor.execute(
                'DELETE FROM conversations WHERE id = ?', (conversation_id,))

            conn.commit()
            conn.close()

            logger.info(f"🗑️ Conversation deleted: {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error deleting conversation: {e}")
            return False

    def export_conversations_csv(self):
        """Export all conversations to CSV format"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM conversations ORDER BY start_time DESC')
            conversations = cursor.fetchall()

            csv_data = "ID,Session ID,Start Time,End Time,Total Messages,On-Topic,Off-Topic,Status\n"
            for row in conversations:
                csv_data += f'{row["id"]},"{row["session_id"]}","{row["start_time"]}","{row["end_time"]}",{row["total_messages"]},{row["on_topic_count"]},{row["off_topic_count"]},"{row["status"]}"\n'

            conn.close()
            return csv_data

        except Exception as e:
            logger.error(f"❌ Error exporting CSV: {e}")
            return None

    def cleanup_old_conversations(self, days=90):
        """Delete conversations older than N days"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            date_cutoff = (datetime.now() - timedelta(days=days)).date()

            cursor.execute(
                'DELETE FROM conversation_messages WHERE conversation_id IN (SELECT id FROM conversations WHERE DATE(start_time) < ?)', (date_cutoff,))
            cursor.execute(
                'DELETE FROM conversations WHERE DATE(start_time) < ?', (date_cutoff,))

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
