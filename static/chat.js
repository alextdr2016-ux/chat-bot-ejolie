document.addEventListener('DOMContentLoaded', function() {
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatBox = document.getElementById('chatBox');

    // Send message on button click
    sendBtn.addEventListener('click', sendMessage);

    // Send message on Enter key
    userInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            sendMessage();
        }
    });

    // Example buttons
    const exampleButtons = document.querySelectorAll('.example-btn');
    exampleButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            userInput.value = this.textContent;
            userInput.focus();
        });
    });

    // ========== XSS PROTECTION ==========
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function sendMessage() {
        const message = userInput.value.trim();
        
        if (!message) {
            alert('Scrie o întrebare!');
            return;
        }

        // Add user message to chat
        addMessage(message, 'user');
        
        // Clear input
        userInput.value = '';
        sendBtn.disabled = true;
        sendBtn.textContent = 'Se trimite...';

        // Send to backend
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        
        .then(data => {
            sendBtn.disabled = false;
            sendBtn.innerHTML = 'Trimite ▶';
    
            // Verifică dacă avem răspuns valid
            if (data && data.response) {
                addMessage(data.response, 'bot');
            } else {
                addMessage('Eroare la comunicare cu serverul.', 'bot');
    }
})
        .catch(error => {
            sendBtn.disabled = false;
            sendBtn.innerHTML = 'Trimite ▶';
            console.error('Eroare:', error);
            addMessage('Eroare la comunicare cu serverul.', 'bot');
        });
    }

    // Function to convert URLs to clickable links (with XSS protection)
    function convertLinksToHTML(text) {
        // FIRST: Escape HTML to prevent XSS
        let html = escapeHtml(text);
        
        // Replace \n with <br>
        html = html.replace(/\n/g, '<br>');
        
        // Regex to find URLs - more aggressive matching
        const urlRegex = /(https?:\/\/[^\s<]+?)([).,!?;:\]]*(?:\s|<br>|$))/g;
        
        // Replace URLs with clickable links
        html = html.replace(urlRegex, function(match, url, trailing) {
            // Clean the URL of any trailing punctuation
            let cleanUrl = url;
            while (cleanUrl && /[).,!?;:\]]$/.test(cleanUrl)) {
                cleanUrl = cleanUrl.slice(0, -1);
            }
            
            // Return link + trailing punctuation
            return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer" style="color: #0066cc; text-decoration: underline; cursor: pointer;">🔗 ${cleanUrl}</a>${trailing}`;
        });
        
        return html;
    }

    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        if (sender === 'bot') {
            // Bot messages: convert links but escape HTML first
            const formattedText = convertLinksToHTML(text);
            messageDiv.innerHTML = `
                <div class="bot-message-content">
                    <strong>Ejolie:</strong>
                    ${formattedText}
                </div>
            `;
        } else {
            // User messages: ALWAYS escape HTML to prevent XSS
            const safeText = escapeHtml(text);
            messageDiv.innerHTML = `
                <div class="user-message-content">
                    <strong>Tu:</strong>
                    ${safeText}
                </div>
            `;
        }

        chatBox.appendChild(messageDiv);
        
        // Scroll to bottom
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});