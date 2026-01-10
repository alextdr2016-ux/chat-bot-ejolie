// ✅ Prevent double initialization (GTM / duplicate script load)
if (window.__ejolieChatInitialized) {
  console.warn("Ejolie chat already initialized. Skipping duplicate init.");
} else {
  window.__ejolieChatInitialized = true;

  document.addEventListener("DOMContentLoaded", function () {
    const userInput = document.getElementById("userInput");
    const sendBtn = document.getElementById("sendBtn");
    const chatBox = document.getElementById("chatBox");

    if (!userInput || !sendBtn || !chatBox) {
      console.warn("Ejolie chat elements not found. Aborting chat init.");
      return;
    }

    // ===== STATE =====
    let isSending = false;
    let lastSendTime = 0;

    // ===== SESSION ID =====
    let sessionId = localStorage.getItem("chatSessionId");
    if (!sessionId) {
      sessionId =
        "session_" +
        Date.now() +
        "_" +
        Math.random().toString(36).substr(2, 9);
      localStorage.setItem("chatSessionId", sessionId);
    }

    // ===== EVENTS =====
    sendBtn.addEventListener("click", function (e) {
      e.preventDefault();
      sendMessage();
    });

    userInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    document.querySelectorAll(".example-btn").forEach((btn) => {
      btn.addEventListener("click", function () {
        userInput.value = this.textContent;
        userInput.focus();
      });
    });

    // ===== XSS =====
    function escapeHtml(text) {
      const div = document.createElement("div");
      div.textContent = text ?? "";
      return div.innerHTML;
    }

    // ===== LINKS =====
    function convertLinksToHTML(text) {
      let html = escapeHtml(text);
      html = html.replace(/\n/g, "<br>");

      const urlRegex = /(https?:\/\/[^\s<]+?)([).,!?;:\]]*(?:\s|<br>|$))/g;

      html = html.replace(urlRegex, function (_, url, trailing) {
        let cleanUrl = url;
        while (/[).,!?;:\]]$/.test(cleanUrl)) {
          cleanUrl = cleanUrl.slice(0, -1);
        }

        return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer"
          style="color:#0066cc;text-decoration:underline;">
          🔗 ${cleanUrl}
        </a>${trailing}`;
      });

      return html;
    }

    // ===== ADD MESSAGE =====
    function addMessage(text, sender) {
      const div = document.createElement("div");
      div.className = `message ${sender}-message`;

      if (sender === "bot") {
        div.innerHTML = `
          <div class="bot-message-content">
            <strong>Ejolie:</strong><br>
            ${convertLinksToHTML(text)}
          </div>
        `;
      } else {
        div.innerHTML = `
          <div class="user-message-content">
            <strong>Tu:</strong><br>
            ${escapeHtml(text)}
          </div>
        `;
      }

      chatBox.appendChild(div);
      chatBox.scrollTop = chatBox.scrollHeight;
    }

    // ===== SEND MESSAGE =====
    async function sendMessage() {
      if (isSending) return;

      const message = userInput.value.trim();
      if (!message) {
        alert("Scrie o întrebare!");
        return;
      }

      // THROTTLE
      const now = Date.now();
      if (now - lastSendTime < 800) return;
      lastSendTime = now;

      isSending = true;

      addMessage(message, "user");
      userInput.value = "";
      sendBtn.disabled = true;
      sendBtn.textContent = "Se trimite...";

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: message,
            session_id: sessionId
            // ✅ IMPORTANT: NU TRIMITEM api_key pentru chat-ul public
          }),
        });

        let data = null;
        try {
          data = await res.json();
        } catch (_) {}

        if (!res.ok) {
          if (res.status === 429) {
            addMessage(
              "⏳ Prea multe cereri. Așteaptă 20-30 secunde și încearcă din nou.",
              "bot"
            );
          } else if (res.status === 403) {
            addMessage(
              "⚠️ Acces refuzat (API key). Te rog contactează suportul.",
              "bot"
            );
          } else {
            addMessage("Eroare la comunicare cu serverul.", "bot");
          }
          return;
        }

        if (data?.session_id) {
          sessionId = data.session_id;
          localStorage.setItem("chatSessionId", sessionId);
        }

        const botText =
          (data && typeof data === "object" && data.response) ||
          "Eroare la comunicare cu serverul.";
        addMessage(botText, "bot");
      } catch (err) {
        addMessage("Eroare la comunicare cu serverul.", "bot");
      } finally {
        isSending = false;
        sendBtn.disabled = false;
        sendBtn.innerHTML = "Trimite ▶";
      }
    }
  });
}
