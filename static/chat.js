<script>
document.addEventListener('DOMContentLoaded', function () {
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatBox = document.getElementById('chatBox');

    // ===== GLOBAL LOCK (ANTI DOUBLE SUBMIT) =====
    let isSending = false;
    let lastSendTime = 0;

    // ===== EVENT LISTENERS =====
    sendBtn.addEventListener('click', sendMessage);

    userInput.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });

    // Example buttons
    document.querySelectorAll('.example-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            userInput.value = this.textContent;
            userInput.focus();
        });
    });

    // ===== XSS PROTECTION =====
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ===== SEND MESSAGE =====
    function sendMessage() {
        const now = Date.now();

        // HARD PROTECTION
        if (isSending) return;
        if (now - lastSendTime < 1000) return;
        lastSendTime = now;

        const message = userInput.value.trim();
        if (!message) {
            alert('Scrie o întrebare!');
            return;
        }

        isSending = true;

        // UI update
        addMessage(message, 'user');
        userInput.value = '';
        sendBtn.disabled = true;
        sendBtn.textContent = 'Se trimite...';

        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
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
                addMessage('⏳ Prea multe cereri. Te rog așteaptă 30 secunde și încearcă din nou.', 'bot');
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

    // ===== LINK PARSER (SAFE) =====
    function convertLinksToHTML(text) {
        let html = escapeHtml(text);
        html = html.replace(/\n/g, '<br>');

        const urlRegex = /(https?:\/\/[^\s<]+?)([).,!?;:\]]*(?:\s|<br>|$))/g;

        html = html.replace(urlRegex, function (match, url, trailing) {
            let cleanUrl = url;
            while (cleanUrl && /[).,!?;:\]]$/.test(cleanUrl)) {
                cleanUrl = cleanUrl.slice(0, -1);
            }

            return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer"
                style="color:#0066cc;text-decoration:underline;cursor:pointer;">
                🔗 ${cleanUrl}
            </a>${trailing}`;
        });

        return html;
    }

    // ===== ADD MESSAGE TO CHAT =====
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        if (sender === 'bot') {
            messageDiv.innerHTML = `
                <div class="bot-message-content">
                    <strong>Ejolie:</strong><br>
                    ${convertLinksToHTML(text)}
                </div>
            `;
        } else {
            messageDiv.innerHTML = `
                <div class="user-message-content">
                    <strong>Tu:</strong><br>
                    ${escapeHtml(text)}
                </div>
            `;
        }

        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});
</script>
