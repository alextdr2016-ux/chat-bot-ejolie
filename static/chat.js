// ============ GLOBAL VARIABLES ============
let sessionId = generateSessionId();

// ============ DOM ELEMENTS ============
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

// ============ HELPER FUNCTIONS ============
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function formatMessage(text) {
    // Convert URLs to clickable links
    return text.replace(
        /(https?:\/\/[^\s]+)/g,
        '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    );
}

// ============ MESSAGE DISPLAY FUNCTIONS ============
function displayUserMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'user-message-content';
    contentDiv.textContent = message;
    
    messageDiv.appendChild(contentDiv);
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function displayBotMessage(message, products = null) {
    // Display text message
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'bot-message-content';
    contentDiv.innerHTML = '<strong>Ejolie:</strong> ' + formatMessage(message);

    messageDiv.appendChild(contentDiv);
    chatBox.appendChild(messageDiv);

    // 🎯 If products exist, display carousel
    if (products && products.length > 0) {
        console.log('📦 Displaying products carousel:', products.length, 'products');
        console.log('📦 Products data:', products);
        const carousel = createProductCarousel(products);
        chatBox.appendChild(carousel);
        console.log('✅ Carousel appended to chatBox');
    } else {
        console.log('⚠️ No products to display');
    }

    chatBox.scrollTop = chatBox.scrollHeight;
}

function displayErrorMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'bot-message-content';
    contentDiv.innerHTML = '<strong>Ejolie:</strong> ⚠️ ' + message;
    
    messageDiv.appendChild(contentDiv);
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ============ PRODUCT CAROUSEL FUNCTIONS ============
function createProductCarousel(products) {
    console.log('Creating carousel with products:', products);
    
    const carouselContainer = document.createElement('div');
    carouselContainer.className = 'product-carousel-container';
    
    // Add class based on number of products
    if (products.length === 1) {
        carouselContainer.classList.add('single-product');
    } else if (products.length <= 2) {
        carouselContainer.classList.add('few-products');
    }
    
    const carousel = document.createElement('div');
    carousel.className = 'product-carousel';
    
    // Create product cards
    products.forEach((product, index) => {
        const card = createProductCard(product, index);
        carousel.appendChild(card);
    });
    
    carouselContainer.appendChild(carousel);
    
    // Add navigation buttons only if more than 2 products
    if (products.length > 2) {
        const prevBtn = document.createElement('button');
        prevBtn.className = 'carousel-btn prev';
        prevBtn.innerHTML = '←';
        prevBtn.setAttribute('aria-label', 'Previous products');
        prevBtn.onclick = () => scrollCarousel(carousel, -1);
        
        const nextBtn = document.createElement('button');
        nextBtn.className = 'carousel-btn next';
        nextBtn.innerHTML = '→';
        nextBtn.setAttribute('aria-label', 'Next products');
        nextBtn.onclick = () => scrollCarousel(carousel, 1);
        
        carouselContainer.appendChild(prevBtn);
        carouselContainer.appendChild(nextBtn);
    }
    
    return carouselContainer;
}

function createProductCard(product, index) {
    const card = document.createElement('div');
    card.className = 'product-card';
    card.setAttribute('data-product-index', index);

    // Product image
    const img = document.createElement('img');
    img.src = product.image || 'https://via.placeholder.com/220x260?text=No+Image';
    img.alt = product.name;

    // ✅ iOS FIX: Remove lazy loading (causes issues on iOS Safari)
    // img.loading = 'lazy';  // Removed for iOS compatibility

    // ✅ iOS FIX: Enhanced error handling
    img.onerror = function() {
        console.warn('Image failed to load:', product.image);
        this.src = 'https://via.placeholder.com/220x260?text=Image+Not+Found';
    };

    // ✅ iOS FIX: Force image decode before display
    if (img.decode) {
        img.decode().catch(() => {
            console.warn('Image decode failed:', product.image);
        });
    }
    
    // Product name
    const name = document.createElement('h4');
    name.textContent = product.name;
    name.title = product.name; // Full name on hover
    
    // Product price
    const price = document.createElement('p');
    price.className = 'price';
    price.textContent = product.price;
    
    // View product button
    const link = document.createElement('a');
    link.href = product.link;
    link.className = 'btn-view';
    link.textContent = 'Vezi Produs';
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    
    // Assemble card
    card.appendChild(img);
    card.appendChild(name);
    card.appendChild(price);
    card.appendChild(link);
    
    return card;
}

function scrollCarousel(carousel, direction) {
    const cardWidth = carousel.querySelector('.product-card').offsetWidth;
    const gap = 16; // Gap between cards
    const scrollAmount = (cardWidth + gap) * direction;
    
    carousel.scrollBy({
        left: scrollAmount,
        behavior: 'smooth'
    });
}

// ============ API FUNCTIONS ============
async function sendMessage() {
    const message = userInput.value.trim();
    
    if (!message) {
        return;
    }
    
    // Display user message
    displayUserMessage(message);
    
    // Clear input and disable button
    userInput.value = '';
    sendBtn.disabled = true;
    sendBtn.textContent = 'Se trimite...';
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Display bot response with products (if any)
        if (data.status === 'success') {
            displayBotMessage(data.response, data.products);
            console.log('Products received:', data.products);
        } else if (data.status === 'rate_limited') {
            displayErrorMessage(data.response);
        } else {
            displayErrorMessage(data.response || 'A apărut o eroare. Te rog încearcă din nou.');
        }
        
    } catch (error) {
        console.error('Error sending message:', error);
        displayErrorMessage('Eroare de conexiune. Verifică conexiunea la internet și încearcă din nou.');
    } finally {
        // Re-enable button
        sendBtn.disabled = false;
        sendBtn.textContent = 'Trimite ▶';
        userInput.focus();
    }
}

// ============ EVENT LISTENERS ============
sendBtn.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Example buttons (if they exist)
const exampleButtons = document.querySelectorAll('.example-btn');
exampleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        userInput.value = btn.textContent.replace(/^\S+\s/, ''); // Remove emoji
        sendMessage();
    });
});

// ============ INITIALIZATION ============
document.addEventListener('DOMContentLoaded', () => {
    console.log('Chat initialized with session:', sessionId);
    userInput.focus();
});