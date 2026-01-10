# ==================== CHAT API ====================

@app.route("/api/chat", methods=["POST"])
@limiter.limit("30 per minute")
def chat():
    try:
        data = request.get_json(silent=True) or {}

        user_message = (data.get("message") or "").strip()
        session_id = data.get("session_id")

        # ✅ HARDENED api_key handling
        api_key = (data.get("api_key") or "").strip()

        if not user_message:
            return jsonify({
                "response": "Te rog scrie un mesaj.",
                "status": "error"
            }), 400

        # =========================
        # SAAS: VALIDARE TENANT (OPTIONAL)
        # =========================
        tenant = None
        if api_key != "":
            tenant = db.get_tenant_by_api_key(api_key)
            if not tenant:
                return jsonify({
                    "response": "API key invalid.",
                    "status": "error"
                }), 403

        tenant_id = tenant["id"] if tenant else "default"

        # =========================
        # BOT RESPONSE
        # =========================
        response = bot.get_response(
            user_message,
            session_id=session_id,
            user_ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")
        )

        if isinstance(response, str):
            try:
                response = json.loads(response)
            except Exception:
                response = {"response": response, "status": "success"}

        if not isinstance(response, dict):
            response = {
                "response": "Eroare internă (format răspuns).",
                "status": "error"
            }

        # =========================
        # SAVE CONVERSATION
        # =========================
        try:
            db.save_conversation(
                session_id=session_id or f"session_{int(datetime.now().timestamp())}",
                user_message=user_message,
                bot_response=response.get("response", ""),
                user_ip=request.remote_addr,
                user_agent=request.headers.get("User-Agent", ""),
                tenant_id=tenant_id
            )
        except Exception:
            logger.warning("⚠️ Failed to save conversation:")
            logger.warning(traceback.format_exc())

        if response.get("status") == "rate_limited":
            return jsonify(response), 429

        return jsonify(response), 200

    except Exception:
        logger.error("❌ Chat error:")
        logger.error(traceback.format_exc())
        return jsonify({
            "response": "A apărut o eroare. Te rog încearcă din nou.",
            "status": "error"
        }), 500
