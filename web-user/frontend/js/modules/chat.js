/**
 * Chat Module - Floating chatbot widget for Vietnamese Traffic Law
 * Connects to backend /api/chat endpoint
 */

import { getCurrentLocation } from './maps.js';

// Chat history for context
let chatHistory = [];

// Welcome message shown when chat opens
const WELCOME_MESSAGE = `Xin chào! 👋 Tôi là **NOVA TRAFFIX** - Trợ lý Luật Giao thông.

🚗 **Tôi có thể giúp bạn:**

📋 **Tra cứu mức phạt** - Hỏi về các vi phạm giao thông
   _Ví dụ: "Vượt đèn đỏ bị phạt bao nhiêu?"_

🪪 **Thông tin bằng lái** - GPLX các hạng, điều kiện
   _Ví dụ: "Bằng B2 được lái xe gì?"_

🍺 **Nồng độ cồn** - Quy định và mức phạt
   _Ví dụ: "Uống rượu lái xe phạt thế nào?"_

⚡ **Tốc độ** - Giới hạn tốc độ các loại đường
   _Ví dụ: "Tốc độ tối đa trong đô thị?"_

📍 **Biển báo & Quy tắc** - Các quy định giao thông

💡 **Mẹo:** Cứ hỏi tự nhiên, tôi sẽ cố gắng trả lời!`;

// Help message for "what can you do"
const HELP_MESSAGE = `🚗 **NOVA TRAFFIX có thể giúp bạn:**

━━━━━━━━━━━━━━━━━━━━━━

📋 **1. TRA CỨU MỨC PHẠT**
Hỏi về bất kỳ vi phạm giao thông nào:
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

📖 **Nguồn thông tin:**
• Nghị định 168/2024/NĐ-CP (mới nhất)
• Luật Trật tự ATGT đường bộ 2024

Hãy hỏi tôi bất cứ điều gì về luật giao thông! 🚦`;

export function initChat() {
    const chatFab = document.getElementById('chat-fab');
    const chatPopup = document.getElementById('chat-popup');
    const chatClose = document.getElementById('chat-close');
    const chatInput = document.getElementById('chat-input');
    const chatSend = document.getElementById('chat-send');
    const chatMessages = document.getElementById('chat-messages');

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
            addMessage('Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại sau.', 'ai');
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

    // Add quick action buttons
    addQuickActions(chatMessages);

    console.log('💬 Chat module initialized with backend API');
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
    messageDiv.style.cssText = `
        padding: 0.75rem 1rem;
        border-radius: 0.75rem;
        margin-bottom: 0.75rem;
        max-width: 90%;
        line-height: 1.5;
        font-size: 0.9rem;
        ${sender === 'user'
            ? 'background: linear-gradient(135deg, #3b82f6, #2563eb); margin-left: auto; color: white;'
            : 'background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); color: #0f172a;'}
    `;
    
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
        // Italic: _text_
        .replace(/_(.*?)_/g, '<em style="color: #64748b; font-size: 0.85em;">$1</em>')
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
    div.style.cssText = `
        margin-top: 0.75rem;
        padding-top: 0.75rem;
        border-top: 1px solid rgba(59, 130, 246, 0.2);
        font-size: 0.8rem;
        color: #64748b;
    `;
    
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
    typingDiv.style.cssText = `
        padding: 0.75rem 1rem;
        border-radius: 0.75rem;
        margin-bottom: 0.75rem;
        max-width: 60%;
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.2);
    `;
    typingDiv.innerHTML = `
        <div style="display: flex; gap: 4px; align-items: center;">
            <span style="color: #64748b;">Đang trả lời</span>
            <span class="typing-dots" style="display: flex; gap: 2px;">
                <span style="width: 6px; height: 6px; background: #3b82f6; border-radius: 50%; animation: typing 1s infinite;"></span>
                <span style="width: 6px; height: 6px; background: #3b82f6; border-radius: 50%; animation: typing 1s infinite 0.2s;"></span>
                <span style="width: 6px; height: 6px; background: #3b82f6; border-radius: 50%; animation: typing 1s infinite 0.4s;"></span>
            </span>
        </div>
    `;
    
    // Add animation style if not exists
    if (!document.getElementById('typing-animation-style')) {
        const style = document.createElement('style');
        style.id = 'typing-animation-style';
        style.textContent = `
            @keyframes typing {
                0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
                30% { opacity: 1; transform: translateY(-3px); }
            }
        `;
        document.head.appendChild(style);
    }
    
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
    actionsDiv.style.cssText = `
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        padding: 0.5rem;
        margin-bottom: 0.5rem;
    `;

    quickActions.forEach(action => {
        const btn = document.createElement('button');
        btn.style.cssText = `
            padding: 0.4rem 0.75rem;
            border-radius: 1rem;
            border: 1px solid rgba(59, 130, 246, 0.3);
            background: rgba(59, 130, 246, 0.1);
            color: #0f172a;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 0.25rem;
        `;
        btn.innerHTML = `${action.icon} ${action.text}`;
        btn.addEventListener('click', () => {
            const chatInput = document.getElementById('chat-input');
            chatInput.value = action.query;
            document.getElementById('chat-send').click();
        });
        btn.addEventListener('mouseenter', () => {
            btn.style.background = 'rgba(59, 130, 246, 0.2)';
            btn.style.borderColor = 'rgba(59, 130, 246, 0.5)';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.background = 'rgba(59, 130, 246, 0.1)';
            btn.style.borderColor = 'rgba(59, 130, 246, 0.3)';
        });
        actionsDiv.appendChild(btn);
    });

    // Insert at the beginning of chat messages area
    chatMessages.parentNode.insertBefore(actionsDiv, chatMessages);
}
