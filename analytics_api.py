"""
Analytics API endpoints for dashboard
Add these routes to main.py
"""

import os
import logging
from flask import jsonify, request
from database import db

logger = logging.getLogger(__name__)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


# ==================== ANALYTICS ENDPOINTS ====================

def setup_analytics_routes(app):
    """Setup all analytics routes"""

    # ====================
    # CONVERSATIONS LIST
    # ====================
    @app.route('/api/admin/analytics/conversations', methods=['GET'])
    def get_conversations():
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            limit = int(request.args.get('limit', 50))
            offset = int(request.args.get('offset', 0))
            tenant_id = request.args.get('tenant_id')  # ⬅️ OPTIONAL

            filters = {}
            if request.args.get('date_from'):
                filters['date_from'] = request.args.get('date_from')
            if request.args.get('date_to'):
                filters['date_to'] = request.args.get('date_to')
            if request.args.get('status'):
                filters['status'] = request.args.get('status')
            if request.args.get('keyword'):
                filters['keyword'] = request.args.get('keyword')

            # tenant-aware, dar compatibil
            conversations, total = db.get_conversations(
                limit=limit,
                offset=offset,
                filters=filters,
                tenant_id=tenant_id
            )

            return jsonify({
                "conversations": conversations,
                "total": total,
                "limit": limit,
                "offset": offset,
                "tenant_id": tenant_id
            }), 200

        except Exception as e:
            logger.error(f"❌ Error fetching conversations: {e}")
            return jsonify({"error": str(e)}), 500

    # ====================
    # CONVERSATION DETAIL
    # ====================
    @app.route('/api/admin/analytics/conversation/<int:conversation_id>', methods=['GET'])
    def get_conversation_detail(conversation_id):
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            messages = db.get_conversation_messages(conversation_id)
            if not messages:
                return jsonify({"error": "Conversation not found"}), 404

            return jsonify({
                "conversation_id": conversation_id,
                "messages": messages
            }), 200

        except Exception as e:
            logger.error(f"❌ Error fetching conversation detail: {e}")
            return jsonify({"error": str(e)}), 500

    # ====================
    # ANALYTICS STATS
    # ====================
    @app.route('/api/admin/analytics/stats', methods=['GET'])
    def get_analytics_stats():
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            days = int(request.args.get('days', 30))
            tenant_id = request.args.get('tenant_id')  # ⬅️ OPTIONAL

            stats = db.get_analytics(days=days, tenant_id=tenant_id)
            daily_stats = db.get_daily_stats(days=days, tenant_id=tenant_id)
            top_questions = db.get_top_questions(limit=10, tenant_id=tenant_id)

            return jsonify({
                "stats": stats,
                "daily_stats": daily_stats,
                "top_questions": top_questions,
                "days": days,
                "tenant_id": tenant_id
            }), 200

        except Exception as e:
            logger.error(f"❌ Error fetching analytics stats: {e}")
            return jsonify({"error": str(e)}), 500

    # ====================
    # EXPORT CSV
    # ====================
    @app.route('/api/admin/analytics/export-csv', methods=['GET'])
    def export_csv():
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            tenant_id = request.args.get('tenant_id')  # ⬅️ OPTIONAL
            csv_data = db.export_conversations_csv(tenant_id=tenant_id)

            if not csv_data:
                return jsonify({"error": "Export failed"}), 500

            return csv_data, 200, {
                'Content-Disposition': 'attachment; filename=conversations.csv',
                'Content-Type': 'text/csv'
            }

        except Exception as e:
            logger.error(f"❌ Error exporting CSV: {e}")
            return jsonify({"error": str(e)}), 500

    # ====================
    # DELETE CONVERSATION
    # ====================
    @app.route('/api/admin/analytics/conversation/<int:conversation_id>', methods=['DELETE'])
    def delete_conversation(conversation_id):
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            success = db.delete_conversation(conversation_id)
            if success:
                return jsonify({"status": "success", "message": "Conversation deleted"}), 200
            return jsonify({"error": "Failed to delete"}), 500

        except Exception as e:
            logger.error(f"❌ Error deleting conversation: {e}")
            return jsonify({"error": str(e)}), 500

    # ====================
    # CLEANUP OLD
    # ====================
    @app.route('/api/admin/analytics/cleanup', methods=['POST'])
    def cleanup_old():
        password = request.args.get('password')
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401

        try:
            days = int(request.args.get('days', 90))
            tenant_id = request.args.get('tenant_id')  # ⬅️ OPTIONAL

            deleted = db.cleanup_old_conversations(
                days=days, tenant_id=tenant_id)

            return jsonify({
                "status": "success",
                "deleted_count": deleted,
                "message": f"Deleted {deleted} conversations older than {days} days",
                "tenant_id": tenant_id
            }), 200

        except Exception as e:
            logger.error(f"❌ Error cleaning up conversations: {e}")
            return jsonify({"error": str(e)}), 500
