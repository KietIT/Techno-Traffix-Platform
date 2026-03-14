/**
 * Chat Module - Floating chatbot widget for Vietnamese Traffic Law
 * Connects to backend /api/chat endpoint
 */

import { getCurrentLocation } from './maps.js';

// Chat history for context
let chatHistory = [];

// Welcome message shown when chat opens
const WELCOME_MESSAGE = `Xin chào! 👋 Tôi là **TECHNO TRAFFIX** — Trợ lý Luật Giao thông đường bộ Việt Nam.

🚗 **TECHNO TRAFFIX có thể giúp bạn:**

📋 **Tra cứu mức phạt** — Hỏi về các vi phạm giao thông
   _Ví dụ: "Vượt đèn đỏ bị phạt bao nhiêu?"_

🪪 **Thông tin bằng lái** — GPLX các hạng, điều kiện
   _Ví dụ: "Bằng B2 được lái xe gì?"_

🍺 **Nồng độ cồn** — Quy định và mức phạt
   _Ví dụ: "Uống rượu lái xe phạt thế nào?"_

⚡ **Tốc độ** — Giới hạn tốc độ các loại đường
   _Ví dụ: "Tốc độ tối đa trong đô thị?"_

📍 **Biển báo & Quy tắc** — Các quy định giao thông

💡 _Cứ hỏi tự nhiên, **TECHNO TRAFFIX** sẽ hỗ trợ bạn!_`;

// Help message for "what can you do"
const HELP_MESSAGE = `🚗 **TECHNO TRAFFIX** có thể giúp bạn những gì?

━━━━━━━━━━━━━━━━━━━━━━

📋 **1. TRA CỨU MỨC PHẠT**
Hỏi **TECHNO TRAFFIX** về bất kỳ vi phạm giao thông nào:
• Vượt đèn đỏ, chạy quá tốc độ
• Không đội mũ bảo hiểm
• Đi ngược chiều, lấn làn
• Không có giấy tờ xe...

💬 _Thử hỏi: "Không đội mũ bảo hiểm phạt bao nhiêu?"_

━━━━━━━━━━━━━━━━━━━━━━

🍺 **2. QUY ĐỊNH NỒNG ĐỘ CỒN**
• Mức phạt theo nồng độ cồn
• Quy định cho xe máy, ô tô
• Tước bằng lái, trừ điểm

💬 _Thử hỏi: "Uống 2 lon bia lái xe bị phạt thế nào?"_

━━━━━━━━━━━━━━━━━━━━━━

🪪 **3. GIẤY PHÉP LÁI XE**
• Các hạng bằng lái (A1, A2, B1, B2, C...)
• Được phép lái xe gì
• Điều kiện thi bằng lái
• Hệ thống trừ điểm GPLX (mới 2025)

💬 _Thử hỏi: "Bằng B2 được lái những xe gì?"_

━━━━━━━━━━━━━━━━━━━━━━

⚡ **4. TỐC ĐỘ & BIỂN BÁO**
• Giới hạn tốc độ theo loại đường
• Quy định đường cao tốc
• Ý nghĩa các biển báo

💬 _Thử hỏi: "Tốc độ tối đa xe máy trong đô thị?"_

━━━━━━━━━━━━━━━━━━━━━━

📖 **Nguồn thông tin của TECHNO TRAFFIX:**
• Nghị định 168/2024/NĐ-CP (mới nhất)
• Luật Trật tự ATGT đường bộ 2024

Hãy hỏi **TECHNO TRAFFIX** bất cứ điều gì về luật giao thông! 🚦`;

export function initChat() {
    const chatFab = document.getElementById('chat-fab');
    const chatPopup = document.getElementById('chat-popup');
    const chatClose = document.getElementById('chat-close');
    const chatExpand = document.getElementById('chat-expand');
    const chatInput = document.getElementById('chat-input');
    const chatSend = document.getElementById('chat-send');
    const chatMessages = document.getElementById('chat-messages');
    const chatScrollBtn = document.getElementById('chat-scroll-btn');
    const chatResizeHandle = document.getElementById('chat-resize-handle');

    if (!chatFab || !chatPopup) {
        console.warn('Chat elements not found');
        return;
    }

    // Toggle chat popup
    chatFab.addEventListener('click', () => {
        const wasOpen = chatPopup.classList.contains('chat-popup--open');
        chatPopup.classList.toggle('chat-popup--open');

        if (!wasOpen) {
            chatInput.focus();
            // Show welcome message on first open
            if (chatMessages.children.length === 0) {
                addMessage(WELCOME_MESSAGE, 'ai');
            }
        }
    });

    chatClose.addEventListener('click', () => {
        chatPopup.classList.remove('chat-popup--open');
    });

    // Expand / collapse toggle
    if (chatExpand) {
        chatExpand.addEventListener('click', () => {
            const isExpanded = chatPopup.classList.toggle('chat-popup--expanded');
            // Remove any inline resize dimensions when toggling
            chatPopup.style.width = '';
            chatPopup.style.height = '';
            // Update icon: expand ↔ collapse
            chatExpand.innerHTML = isExpanded
                ? `<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                     <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                       d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5" />
                   </svg>`
                : `<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                     <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                       d="M4 8V4h4M20 8V4h-4M4 16v4h4M20 16v4h-4" />
                   </svg>`;
            chatExpand.title = isExpanded ? 'Thu nhỏ' : 'Mở rộng';
            // Auto-scroll to bottom after resize
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // Drag-to-resize from top-left corner
    if (chatResizeHandle) {
        initResize(chatPopup, chatResizeHandle, chatMessages);
    }

    // Scroll-to-bottom button visibility
    if (chatScrollBtn && chatMessages) {
        chatMessages.addEventListener('scroll', () => {
            const distFromBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
            if (distFromBottom > 100) {
                chatScrollBtn.style.display = '';
                chatScrollBtn.classList.add('chat-scroll-btn--visible');
            } else {
                chatScrollBtn.classList.remove('chat-scroll-btn--visible');
                // Hide after fade-out transition
                setTimeout(() => {
                    if (!chatScrollBtn.classList.contains('chat-scroll-btn--visible')) {
                        chatScrollBtn.style.display = 'none';
                    }
                }, 200);
            }
        });

        chatScrollBtn.addEventListener('click', () => {
            chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
        });
    }

    // Send message
    const sendMessage = async () => {
        const message = chatInput.value.trim();
        if (!message) return;

        // Add user message
        addMessage(message, 'user');
        chatInput.value = '';
        chatInput.disabled = true;
        chatSend.disabled = true;

        // Show typing indicator
        const typingId = showTypingIndicator();

        try {
            // Check for help/capability questions first (local response)
            const helpResponse = checkHelpQuestion(message);
            if (helpResponse) {
                removeTypingIndicator(typingId);
                addMessage(helpResponse, 'ai');
                chatInput.disabled = false;
                chatSend.disabled = false;
                chatInput.focus();
                return;
            }

            // Call backend API
            const response = await callChatAPI(message);
            removeTypingIndicator(typingId);

            // Format and display response
            const formattedResponse = formatResponse(response);
            addMessage(formattedResponse, 'ai', response.sources);

            // Update chat history
            chatHistory.push(
                { role: 'user', content: message },
                { role: 'assistant', content: response.content }
            );

            // Keep only last 10 messages for context
            if (chatHistory.length > 10) {
                chatHistory = chatHistory.slice(-10);
            }

        } catch (error) {
            console.error('Chat error:', error);
            removeTypingIndicator(typingId);
            addMessage('**TECHNO TRAFFIX** xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại sau.', 'ai');
        }

        chatInput.disabled = false;
        chatSend.disabled = false;
        chatInput.focus();
    };

    chatSend.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }
    });

    // Escape key to close chat
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && chatPopup.classList.contains('chat-popup--open')) {
            chatPopup.classList.remove('chat-popup--open');
        }
    });

    // Add quick action buttons
    addQuickActions(chatMessages);

    // Wire up overview page buttons that open the chatbot
    const openChatFromOverview = () => {
        if (!chatPopup.classList.contains('chat-popup--open')) {
            chatPopup.classList.add('chat-popup--open');
            chatInput.focus();
            if (chatMessages.children.length === 0) {
                addMessage(WELCOME_MESSAGE, 'ai');
            }
        }
    };

    const overviewChatBtn = document.getElementById('overview-open-chat');
    if (overviewChatBtn) {
        overviewChatBtn.addEventListener('click', openChatFromOverview);
    }

    const featureChatCard = document.getElementById('feature-chatbot');
    if (featureChatCard) {
        featureChatCard.addEventListener('click', openChatFromOverview);
    }

    console.log('💬 Chat module initialized with backend API');
}

/**
 * Initialize drag-to-resize from the top-left corner
 */
function initResize(chatPopup, handle, chatMessages) {
    let isResizing = false;
    let startX, startY, startWidth, startHeight;

    handle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        isResizing = true;
        startX = e.clientX;
        startY = e.clientY;
        startWidth = chatPopup.offsetWidth;
        startHeight = chatPopup.offsetHeight;
        chatPopup.classList.add('chat-popup--resizing');
        document.body.style.cursor = 'nw-resize';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        // Dragging top-left: moving left increases width, moving up increases height
        const deltaX = startX - e.clientX;
        const deltaY = startY - e.clientY;
        const newWidth = Math.max(340, Math.min(800, startWidth + deltaX));
        const newHeight = Math.max(400, Math.min(window.innerHeight * 0.9, startHeight + deltaY));
        chatPopup.style.width = newWidth + 'px';
        chatPopup.style.height = newHeight + 'px';
    });

    document.addEventListener('mouseup', () => {
        if (!isResizing) return;
        isResizing = false;
        chatPopup.classList.remove('chat-popup--resizing');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });

    // Touch support for tablets
    handle.addEventListener('touchstart', (e) => {
        const touch = e.touches[0];
        isResizing = true;
        startX = touch.clientX;
        startY = touch.clientY;
        startWidth = chatPopup.offsetWidth;
        startHeight = chatPopup.offsetHeight;
        chatPopup.classList.add('chat-popup--resizing');
    }, { passive: true });

    document.addEventListener('touchmove', (e) => {
        if (!isResizing) return;
        const touch = e.touches[0];
        const deltaX = startX - touch.clientX;
        const deltaY = startY - touch.clientY;
        const newWidth = Math.max(340, Math.min(800, startWidth + deltaX));
        const newHeight = Math.max(400, Math.min(window.innerHeight * 0.9, startHeight + deltaY));
        chatPopup.style.width = newWidth + 'px';
        chatPopup.style.height = newHeight + 'px';
    }, { passive: true });

    document.addEventListener('touchend', () => {
        if (!isResizing) return;
        isResizing = false;
        chatPopup.classList.remove('chat-popup--resizing');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

/**
 * Check if user is asking about capabilities
 */
function checkHelpQuestion(message) {
    const lowerMessage = message.toLowerCase();

    const helpPatterns = [
        'bạn có thể làm gì',
        'bạn làm được gì',
        'giúp gì được',
        'hỗ trợ gì',
        'chức năng',
        'tính năng',
        'help',
        'hướng dẫn',
        'cách sử dụng',
        'sử dụng thế nào',
        'dùng như thế nào',
        'what can you do',
        'làm được những gì',
        'hỏi gì được',
        'hỏi được gì',
    ];

    for (const pattern of helpPatterns) {
        if (lowerMessage.includes(pattern)) {
            return HELP_MESSAGE;
        }
    }

    return null;
}

/**
 * Call backend chat API
 */
async function callChatAPI(message) {
    const payload = {
        message: message,
        chat_history: chatHistory,
    };

    // Attach GPS location if available
    const loc = getCurrentLocation();
    if (loc) {
        payload.location = { lat: loc.lat, lng: loc.lng };
    }

    const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || 'Unknown error');
    }

    return data.data;
}

/**
 * Format response for display
 */
function formatResponse(response) {
    let content = response.content;

    // If topic was rejected, the content already has the rejection message
    if (!response.topic_valid) {
        return content;
    }

    return content;
}

/**
 * Add message to chat
 */
function addMessage(text, sender, sources = null) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');

    messageDiv.className = `chat-message chat-message--${sender}`;

    // Parse markdown-like formatting
    const formattedText = formatMarkdown(text);
    messageDiv.innerHTML = formattedText;

    // Add sources if available
    if (sources && sources.length > 0 && sender === 'ai') {
        const sourcesDiv = createSourcesSection(sources);
        messageDiv.appendChild(sourcesDiv);
    }

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Simple markdown formatter
 */
function formatMarkdown(text) {
    return text
        // Bold: **text**
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Italic: _text_ (styled via CSS .chat-message em)
        .replace(/_(.*?)_/g, '<em>$1</em>')
        // Line breaks
        .replace(/\n/g, '<br>')
        // Bullet points
        .replace(/^• /gm, '&nbsp;&nbsp;• ')
        // Emojis spacing
        .replace(/([\u{1F300}-\u{1F9FF}])/gu, ' $1 ');
}

/**
 * Create sources section
 */
function createSourcesSection(sources) {
    const div = document.createElement('div');
    div.className = 'chat-sources';

    const topSources = sources.slice(0, 2);
    if (topSources.length > 0) {
        div.innerHTML = `
            <div style="margin-bottom: 0.25rem;">📚 <strong>Nguồn tham khảo:</strong></div>
            ${topSources.map(s => `<div style="margin-left: 1rem;">• ${s.source}</div>`).join('')}
        `;
    }

    return div;
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const chatMessages = document.getElementById('chat-messages');
    const typingDiv = document.createElement('div');
    const typingId = 'typing-' + Date.now();

    typingDiv.id = typingId;
    typingDiv.className = 'chat-typing';
    typingDiv.innerHTML = `
        <div style="display: flex; gap: 6px; align-items: center;">
            <span class="chat-typing__label">Đang trả lời</span>
            <span style="display: flex; gap: 3px;">
                <span class="chat-typing__dot"></span>
                <span class="chat-typing__dot"></span>
                <span class="chat-typing__dot"></span>
            </span>
        </div>
    `;

    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return typingId;
}

/**
 * Remove typing indicator
 */
function removeTypingIndicator(typingId) {
    const typingDiv = document.getElementById(typingId);
    if (typingDiv) {
        typingDiv.remove();
    }
}

/**
 * Add quick action buttons for common questions
 */
function addQuickActions(chatMessages) {
    const quickActions = [
        { icon: '🚦', text: 'Vượt đèn đỏ', query: 'Vượt đèn đỏ bị phạt bao nhiêu?' },
        { icon: '🍺', text: 'Nồng độ cồn', query: 'Uống rượu bia lái xe bị phạt thế nào?' },
        { icon: '⚡', text: 'Tốc độ', query: 'Giới hạn tốc độ trong đô thị là bao nhiêu?' },
        { icon: '🪪', text: 'Bằng lái', query: 'Bằng B2 được lái xe gì?' },
    ];

    const actionsDiv = document.createElement('div');
    actionsDiv.id = 'quick-actions';

    quickActions.forEach(action => {
        const btn = document.createElement('button');
        btn.innerHTML = `${action.icon} ${action.text}`;
        btn.addEventListener('click', () => {
            const chatInput = document.getElementById('chat-input');
            chatInput.value = action.query;
            document.getElementById('chat-send').click();
        });
        actionsDiv.appendChild(btn);
    });

    // Insert before the chat-messages-wrapper (which contains chat-messages)
    const wrapper = chatMessages.closest('.chat-messages-wrapper') || chatMessages.parentNode;
    wrapper.parentNode.insertBefore(actionsDiv, wrapper);
}
