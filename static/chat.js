// ✅ Prevent double initialization (GTM / duplicate script load)
if (window.__ejolieChatInitialized) {
  console.warn("Ejolie chat already initialized. Skipping duplicate init.");
} else {
  window.__ejolieChatInitialized = true;

  document.addEventListener('DOMContentLoaded', function () {
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatBox = document.getElementById('chatBox');

    if (!userInput || !sendBtn || !chatBox) {
      console.warn("Ejolie chat elements not found. Aborting chat init.");
      return;
    }

    // ======================
    // CONFIG (TEMPORAR)
    // ======================
    // ⚠️ În viitor va veni din backend / admin
    const API_KEY = "TEST_API_KEY_DE_LA_TENANT";

    // ======================
    // STATE
    // ======================
    let isSending = false;
    let lastSendTime = 0;

    // ======================
    // SESSION ID
    // ======================
    let sessionId = localStorage.getItem('chatSessionId');
    if (!sessionId) {
      sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('chatSessionId', sessionId);
    }
    console.log('📌 Session ID:', sessionId);

    // ======================
    // EVENTS
    // ======================
    sendBtn.addEventListener('click', function (e) {
      e.preventDefault();
      sendMessage();
    });

    userInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    document.querySelectorAll('.example-btn').forEach(btn => {
      btn.addEventListener('click', function () {
        userInput.value = this.textContent;
        userInput.focus();
      });
    });

    // ======================
    // XSS PROTECTION
    // ======================
    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text ?? '';
      return div.innerHTML;
    }

    // ======================
    // NORMALIZE RESPONSE
    // ======================
    function normalizeBotText(data) {
      if (typeof data === 'string') return data;

      if (data && typeof data === 'object') {
        if (data.status === 'rate_limited') {
          return '⏳ Prea multe cereri. Așteaptă 20-30 secunde și încearcă din nou.';
        }

        let resp = data.response;

        if (resp && typeof resp === 'object') {
          if (resp.status === 'rate_limited') {
            return '⏳ Prea multe cereri. Așteaptă 20-30 secunde și încearcă din nou.';
          }
          return resp.response || JSON.stringify(resp);
        }

        if (typeof resp === 'string') {
          const s = resp.trim();
          if (s.startsWith('{') && s.endsWith('}')) {
            try {
              const inner = JSON.parse(s);
              if (inner?.status === 'rate_limited') {
                return '⏳ Prea multe cereri. Așteaptă 20-30 secunde și încearcă din nou.';
              }
              if (inner?.response) return inner.response;
            } catch (_) {}
          }

          if (resp.includes('\\u')) {
            try {
              return JSON.parse('"' + resp.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"');
            } catch (_) {}
          }

          return resp;
        }
      }

      return 'Eroare la comunicare cu serverul.';
    }

    // ======================
    // SEND MESSAGE
    // ======================
    function sendMessage() {
      if (isSending) return;

      const message = userInput.value.trim();
      if (!message) {
        alert('Scrie o întrebare!');
        return;
      }

      const now = Date.now();
      if (now - lastSendTime < 800) return;
      lastSendTime = now;

      isSending = true;

      addMessage(message, 'user');
      userInput.value = '';
      sendBtn.disabled = true;
      sendBtn.textContent = 'Se trimite...';

      fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: message,
          session_id: sessionId,
          api_key: API_KEY
        })
      })
        .then(async response => {
          let data = null;
          try {
            data = await response.json();
          } catch (_) {}

          if (!response.ok) {
            if (response.status === 429) {
              throw new Error('RATE_LIMIT');
            }
            throw new Error('SERVER_ERROR');
          }

          return data;
        })
        .then(data => {
          if (data?.session_id) {
            sessionId = data.session_id;
            localStorage.setItem('chatSessionId', sessionId);
          }

          const botText = normalizeBotText(data);
          addMessage(botText, 'bot');
        })
        .catch(err => {
          if (err.message === 'RATE_LIMIT') {
            addMessage('⏳ Prea multe cereri. Așteaptă 20-30 secunde și încearcă din nou.', 'bot');
          } else {
            addMessage('Eroare la comunicare cu serverul.', 'bot');
          }
        })
        .finally(() => {
          isSending = false;
          sendBtn.disabled = false;
          sendBtn.innerHTML = 'Trimite ▶';
        });
    }

    // ======================
    // LINKIFY
    // ======================
    function convertLinksToHTML(text) {
      let html = escapeHtml(text);
      html = html.replace(/\n/g, '<br>');

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

    // ======================
    // ADD MESSAGE
    // ======================
    function addMessage(text, sender) {
      const div = document.createElement('div');
      div.className = `message ${sender}-message`;

      if (sender === 'bot') {
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
  });
}
