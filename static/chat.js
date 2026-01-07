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
            
            if (data.status === 'success') {
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

    // Function to convert URLs to clickable links
    function convertLinksToHTML(text) {
        // Replace \n with <br>
        let html = text.replace(/\n/g, '<br>');
        
        // Regex to find URLs - EXCLUDING trailing punctuation like ), ., , etc
        // [^\s).,!?;:] means: match anything EXCEPT whitespace, ), ., comma, !, ?, ;, :
        const urlRegex = /(https?:\/\/[^\s).,!?;:]+)/g;
        
        // Replace URLs with clickable links
        html = html.replace(urlRegex, function(url) {
            return `<a href="${url}" target="_blank" style="color: #0066cc; text-decoration: underline; cursor: pointer;">🔗 ${url}</a>`;
        });
        
        return html;
    }

    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        if (sender === 'bot') {
            const formattedText = convertLinksToHTML(text);
            messageDiv.innerHTML = `
                <div class="bot-message-content">
                    <strong>Ejolie:</strong>
                    ${formattedText}
                </div>
            `;
        } else {
            messageDiv.innerHTML = `
                <div class="user-message-content">
                    <strong>Tu:</strong>
                    ${text}
                </div>
            `;
        }

        chatBox.appendChild(messageDiv);
        
        // Scroll to bottom
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});