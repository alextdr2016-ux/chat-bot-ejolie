document.addEventListener('DOMContentLoaded', function () {
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatBox = document.getElementById('chatBox');

    // ===== STATE =====
    let isSending = false;
    let lastSendTime = 0;

    // ===== EVENTS =====
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

    // ===== XSS =====
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ===== SEND MESSAGE =====
    function sendMessage() {
        // LOCK REAL
        if (isSending) return;

        const message = userInput.value.trim();
        if (!message) {
            alert('Scrie o întrebare!');
            return;
        }

        // THROTTLE SIGUR (după validare)
        const now = Date.now();
        if (now - lastSendTime < 800) return;
        lastSendTime = now;

        isSending = true;

        // UI
        addMessage(message, 'user');
        userInput.value = '';
        sendBtn.disabled = true;
        sendBtn.textContent = 'Se trimite...';

        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        })
        .then(async response => {
            const data = await response.json();

            if (!response.ok) {
                if (response.status === 429) {
                    throw new Error('RATE_LIMIT');
                }
                throw new Error('SERVER_ERROR');
            }

            return data;
        })
        .then(data => {
            if (data && data.response) {
                addMessage(data.response, 'bot');
            } else {
                addMessage('Eroare la comunicare cu serverul.', 'bot');
            }
        })
        .catch(err => {
            if (err.message === 'RATE_LIMIT') {
                addMessage('⏳ Prea multe cereri. Așteaptă câteva secunde și încearcă din nou.', 'bot');
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

    // ===== LINKS =====
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

    // ===== ADD MESSAGE =====
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
