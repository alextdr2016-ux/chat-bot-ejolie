"""
Analytics API endpoints for dashboard
Add these routes to main.py
"""

import os
from flask import jsonify, request
from database import db
import logging
import csv
import io

logger = logging.getLogger(__name__)


ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')


# ==================== ANALYTICS ENDPOINTS ====================

def setup_analytics_routes(app):
    """Setup all analytics routes"""

    @app.route('/api/admin/analytics/conversations', methods=['GET'])
    def get_conversations():
        """Get all conversations with filters"""
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            limit = int(request.args.get('limit', 50))
            offset = int(request.args.get('offset', 0))

            filters = {}
            if request.args.get('date_from'):
                filters['date_from'] = request.args.get('date_from')
            if request.args.get('date_to'):
                filters['date_to'] = request.args.get('date_to')
            if request.args.get('status'):
                filters['status'] = request.args.get('status')
            if request.args.get('keyword'):
                filters['keyword'] = request.args.get('keyword')

            conversations, total = db.get_conversations(
                limit=limit, offset=offset, filters=filters)

            logger.info(f"✅ Fetched {len(conversations)} conversations")

            return jsonify({
                "conversations": conversations,
                "total": total,
                "limit": limit,
                "offset": offset
            }), 200

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/analytics/conversation/<int:conversation_id>', methods=['GET'])
    def get_conversation_detail(conversation_id):
        """Get full conversation with messages"""
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            conversations, _ = db.get_conversations(
                limit=1, offset=0, filters=None)
            # Find specific conversation
            conversation = None
            for conv in conversations:
                if conv['id'] == conversation_id:
                    conversation = conv
                    break

            if not conversation:
                return jsonify({"error": "Conversation not found"}), 404

            messages = db.get_conversation_messages(conversation_id)

            return jsonify({
                "conversation": conversation,
                "messages": messages
            }), 200

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/analytics/stats', methods=['GET'])
    def get_analytics_stats():
        """Get overall analytics stats"""
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            days = int(request.args.get('days', 30))
            stats = db.get_analytics(days=days)
            daily_stats = db.get_daily_stats(days=days)
            top_questions = db.get_top_questions(limit=10)

            return jsonify({
                "stats": stats,
                "daily_stats": daily_stats,
                "top_questions": top_questions,
                "days": days
            }), 200

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/analytics/export-csv', methods=['GET'])
    def export_csv():
        """Export conversations to CSV"""
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            csv_data = db.export_conversations_csv()

            if not csv_data:
                return jsonify({"error": "Export failed"}), 500

            return csv_data, 200, {
                'Content-Disposition': 'attachment; filename=conversations.csv',
                'Content-Type': 'text/csv'
            }

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/analytics/conversation/<int:conversation_id>', methods=['DELETE'])
    def delete_conversation(conversation_id):
        """Delete a conversation"""
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            success = db.delete_conversation(conversation_id)

            if success:
                logger.info(f"✅ Conversation {conversation_id} deleted")
                return jsonify({"status": "success", "message": "Conversation deleted"}), 200
            else:
                return jsonify({"error": "Failed to delete"}), 500

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/analytics/cleanup', methods=['POST'])
    def cleanup_old():
        """Delete conversations older than N days"""
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            days = int(request.args.get('days', 90))
            deleted = db.cleanup_old_conversations(days=days)

            logger.info(f"✅ Cleaned up {deleted} old conversations")

            return jsonify({
                "status": "success",
                "deleted_count": deleted,
                "message": f"Deleted {deleted} conversations older than {days} days"
            }), 200

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return jsonify({"error": str(e)}), 500


# Call this in main.py:
# from analytics_api import setup_analytics_routes
# setup_analytics_routes(app)
