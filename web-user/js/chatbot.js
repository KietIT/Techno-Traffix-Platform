/**
 * AI Chatbot Module - HYBRID BRAIN
 * Combines local traffic data analysis with Gemini AI for general questions
 * Handles Vietnamese Traffic Law knowledge and real-time traffic context
 */

// ⚠️ IMPORTANT: Replace with your actual Gemini API key
const GEMINI_API_KEY = 'AIzaSyDKzriUsUqifwXN4Fusi5Y_jmuT2VwZJ74'; // TODO: Replace with your key

// Chatbot state
let chatHistory = [];
let isProcessing = false;

/**
 * Clean and format markdown-style text to HTML
 * Converts ** to <strong>, removes raw markdown artifacts
 * @param {string} text - Raw text with markdown
 * @returns {string} HTML formatted text
 */
function formatBotMessage(text) {
    // Convert **text** to <strong>text</strong>
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Convert emoji + text patterns to bold without asterisks
    text = text.replace(/⚠️\s*([^\n:]+):/g, '⚠️ <strong>$1:</strong>');
    text = text.replace(/📍\s*([^\n:]+):/g, '📍 <strong>$1:</strong>');
    text = text.replace(/🚦\s*([^\n:]+):/g, '🚦 <strong>$1:</strong>');
    text = text.replace(/📊\s*([^\n:]+):/g, '📊 <strong>$1:</strong>');
    text = text.replace(/💡\s*([^\n:]+):/g, '💡 <strong>$1:</strong>');
    text = text.replace(/✅\s*([^\n:]+):/g, '✅ <strong>$1:</strong>');
    text = text.replace(/🔴/g, '<span style="color: #DC2626;">🔴</span>');
    text = text.replace(/🟠/g, '<span style="color: #F59E0B;">🟠</span>');
    
    // Convert line breaks to <br>
    text = text.replace(/\n/g, '<br>');
    
    return text;
}

/**
 * Initialize chatbot interface
 */
function initializeChatbot() {
    const chatContainer = document.getElementById('chat-messages');
    if (!chatContainer) return;
    
    // Add welcome message if chat is empty
    if (chatHistory.length === 0) {
        addBotMessage(
            '👋 Xin chào! Tôi là trợ lý AI của NOVA TRAFFIX.\n\n' +
            'Tôi có thể giúp bạn:\n' +
            '• Tra cứu luật giao thông Việt Nam\n' +
            '• Kiểm tra tình trạng giao thông tại các vị trí cụ thể\n' +
            '• Tư vấn về mức phạt vi phạm giao thông\n\n' +
            'Hãy hỏi tôi bất cứ điều gì về giao thông! 🚗'
        );
    }
}

/**
 * Add message to chat history and UI
 * CRITICAL: Bot messages use innerHTML to render HTML tags (<b>, <br>, <strong>)
 * @param {string} message - Message content
 * @param {string} sender - 'user' or 'bot'
 * @param {boolean} isWarning - Whether message is a warning
 */
function addMessage(message, sender, isWarning = false) {
    const chatContainer = document.getElementById('chat-messages');
    if (!chatContainer) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}`;
    if (isWarning && sender === 'bot') {
        messageDiv.classList.add('warning');
    }
    
    // CRITICAL: Bot messages render HTML, user messages are plain text (XSS protection)
    if (sender === 'bot') {
        messageDiv.innerHTML = formatBotMessage(message); // Allows <b>, <br>, <strong> rendering
    } else {
        messageDiv.textContent = message; // Escapes HTML for security
    }
    
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // Add to history
    chatHistory.push({ sender, message, timestamp: new Date().toISOString() });
}

/**
 * Add user message
 * @param {string} message - Message content
 */
function addUserMessage(message) {
    addMessage(message, 'user');
}

/**
 * Add bot message
 * @param {string} message - Message content
 * @param {boolean} isWarning - Whether message is a warning
 */
function addBotMessage(message, isWarning = false) {
    addMessage(message, 'bot', isWarning);
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const chatContainer = document.getElementById('chat-messages');
    if (!chatContainer) return;
    
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typing-indicator';
    typingDiv.className = 'chat-message bot';
    typingDiv.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    
    chatContainer.appendChild(typingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

/**
 * Hide typing indicator
 */
function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Process user query and generate response - HYBRID BRAIN
 * Step A: Check for traffic-specific keywords (local data)
 * Step B: If traffic-related, query local SIMULATED_TRAFFIC_DATA
 * Step C: Otherwise, call Gemini API for general questions
 * @param {string} query - User's question
 * @returns {Promise<Object>} Response object
 */
async function processQuery(query) {
    const lowerQuery = query.toLowerCase();
    
    // STEP A: Keyword detection for traffic context (10km radius filter)
    const trafficKeywords = [
        'kẹt', 'tắc', 'ùn', 'đông', 'ùn tắc', 'ùn ứ', 'tắc nghẽn',
        'đường nào', 'tuyến nào', 'đoạn nào',
        'vị trí', 'tại đâu', 'ở đâu',
        'gần tôi', 'quanh tôi', 'gần đây',
        'dak lak', 'đắk lắk', 'phạm hùng',
        'hiện tại', 'bây giờ', 'đang'
    ];
    
    const isTrafficQuery = trafficKeywords.some(keyword => lowerQuery.includes(keyword));
    
    // STEP B: Local traffic data handling
    if (isTrafficQuery) {
        console.log('🔍 Detected traffic-related query, using local data');
        
        // Check for user location queries
        if ((lowerQuery.includes('vị trí') && (lowerQuery.includes('tôi') || lowerQuery.includes('của tôi') || lowerQuery.includes('hiện tại'))) ||
            lowerQuery.includes('gần tôi') ||
            lowerQuery.includes('quanh tôi') ||
            (lowerQuery.includes('đây') && lowerQuery.includes('giao thông'))) {
            return handleUserLocationQuery(query);
        }
        
        // Check for Dak Lak location queries
        if (lowerQuery.includes('đắk lắk') || 
            lowerQuery.includes('dak lak') || 
            lowerQuery.includes('phạm hùng') || 
            lowerQuery.includes('pham hung') ||
            lowerQuery.includes('tân an')) {
            return handleDakLakQuery(query);
        }
        
        // Check for general traffic status query
        if (lowerQuery.includes('giao thông') && 
            (lowerQuery.includes('hiện tại') || lowerQuery.includes('bây giờ') || lowerQuery.includes('đang') || lowerQuery.includes('tổng hợp'))) {
            return handleCurrentTrafficQuery();
        }
        
        // Default to comprehensive traffic report
        return handleCurrentTrafficQuery();
    }
    
    // Check for hard-coded traffic law queries (high-priority local knowledge)
    if (lowerQuery.includes('phạt') || lowerQuery.includes('vi phạm') || lowerQuery.includes('mức phạt')) {
        return handleTrafficViolationQuery(lowerQuery);
    }
    
    if (lowerQuery.includes('tốc độ') || lowerQuery.includes('giới hạn')) {
        return handleSpeedLimitQuery(lowerQuery);
    }
    
    if (lowerQuery.includes('nồng độ cồn') || lowerQuery.includes('rượu bia') || lowerQuery.includes('say rượu')) {
        return handleAlcoholQuery();
    }
    
    if (lowerQuery.includes('mũ bảo hiểm') || lowerQuery.includes('bảo hiểm')) {
        return handleHelmetQuery();
    }
    
    if (lowerQuery.includes('vượt đèn đỏ') || lowerQuery.includes('đèn đỏ')) {
        return handleRedLightQuery();
    }
    
    if (lowerQuery.includes('giấy phép') || lowerQuery.includes('bằng lái')) {
        return handleLicenseQuery();
    }
    
    // STEP C: General questions → Call Gemini API
    console.log('🤖 General question detected, calling Gemini API');
    return await callGeminiAPI(query);
}

/**
 * Call Gemini API for general traffic law questions
 * @param {string} query - User's question
 * @returns {Promise<Object>} Response object
 */
async function callGeminiAPI(query) {
    try {
        const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_API_KEY}`;
        
        const systemPrompt = `Bạn là trợ lý giao thông thông minh của hệ thống NOVA TRAFFIX. 
Nhiệm vụ của bạn là trả lời ngắn gọn, chính xác về luật giao thông Việt Nam, an toàn giao thông, và các câu hỏi liên quan đến phương tiện.
- Trả lời bằng tiếng Việt có dấu
- Ngắn gọn, dễ hiểu (tối đa 150 từ)
- Tập trung vào thông tin thực tế và hữu ích
- Sử dụng emoji phù hợp để làm nổi bật
- Nếu không chắc chắn, hãy khuyên người dùng tham khảo luật giao thông chính thức`;
        
        const requestBody = {
            contents: [{
                parts: [{
                    text: `${systemPrompt}\n\nCâu hỏi: ${query}`
                }]
            }],
            generationConfig: {
                temperature: 0.7,
                maxOutputTokens: 500,
                topP: 0.9,
                topK: 40
            }
        };
        
        console.log('🔄 Calling Gemini API...');
        
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody),
            signal: AbortSignal.timeout(15000) // 15 second timeout
        });
        
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('API_KEY_INVALID');
            } else if (response.status === 429) {
                throw new Error('RATE_LIMIT');
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        }
        
        const data = await response.json();
        
        if (data.candidates && data.candidates[0] && data.candidates[0].content) {
            const geminiResponse = data.candidates[0].content.parts[0].text;
            console.log('✅ Gemini API response received');
            
            return {
                message: `🤖 **Trợ lý AI trả lời:**\n\n${geminiResponse}`,
                isWarning: false
            };
        } else {
            throw new Error('Invalid response format');
        }
        
    } catch (error) {
        console.error('❌ Gemini API error:', error);
        
        // Graceful error handling
        if (error.message === 'API_KEY_INVALID') {
            return {
                message: '⚠️ **Lỗi xác thực API**\n\nAPI Key không hợp lệ hoặc đã hết hạn. Vui lòng liên hệ quản trị viên để cập nhật.\n\n' +
                         'Trong thời gian chờ, bạn có thể hỏi tôi về:\n' +
                         '• Tình trạng giao thông tại Đắk Lắk hoặc vị trí của bạn\n' +
                         '• Mức phạt vi phạm, tốc độ, nồng độ cồn\n' +
                         '• Các quy định về bằng lái, mũ bảo hiểm',
                isWarning: true
            };
        } else if (error.message === 'RATE_LIMIT') {
            return {
                message: '⏳ **Hệ thống đang quá tải**\n\nVui lòng thử lại sau ít phút.\n\n' +
                         'Bạn vẫn có thể hỏi về tình trạng giao thông hiện tại bằng cách gõ: "Giao thông hiện tại như thế nào?"',
                isWarning: false
            };
        } else {
            return {
                message: '❌ **Không thể kết nối với AI**\n\n' +
                         'Đã xảy ra lỗi khi kết nối với Gemini API. Vui lòng thử lại sau.\n\n' +
                         '💡 Bạn có thể hỏi về:\n' +
                         '• "Giao thông gần tôi như thế nào?"\n' +
                         '• "Tình trạng đường tại Đắk Lắk"\n' +
                         '• "Mức phạt vượt đèn đỏ"',
                isWarning: false
            };
        }
    }
}

/**
 * Handle user location queries WITH STREET NAMES (Defensive Programming)
 * STEP B: Query local SIMULATED_TRAFFIC_DATA and filter within 5km radius
 * @param {string} query - User query
 * @returns {Object} Response object
 */
function handleUserLocationQuery(query) {
    // Validate that TrafficDataModule exists
    if (!window.TrafficDataModule || !window.TrafficDataModule.analyzeTrafficAtLocation) {
        return {
            message: '⚠️ Mô-đun phân tích giao thông chưa sẵn sàng. Vui lòng tải lại trang.',
            isWarning: true
        };
    }
    
    // Validate that SIMULATED_TRAFFIC_DATA exists
    if (!window.SIMULATED_TRAFFIC_DATA || !window.SIMULATED_TRAFFIC_DATA.userLocation) {
        return {
            message: '⏳ Dữ liệu giao thông đang được tải, vui lòng thử lại sau giây lát.',
            isWarning: false
        };
    }
    
    try {
        const analysis = window.TrafficDataModule.analyzeTrafficAtLocation('userLocation');
        
        console.log('🔍 User Location Analysis:', analysis);
        console.log('📊 Total segments:', analysis.totalSegments);
        console.log('🔴 Severe segments:', analysis.severeSegmentCount);
        console.log('🟠 Moderate segments:', analysis.moderateSegmentCount);
        
        let response = '📍 Tình trạng giao thông gần vị trí của bạn:\n\n';
        
        if (analysis.status === 'unknown') {
            response += analysis.message;
            return { message: response, isWarning: false };
        }
        
        // Add the detailed message with street names
        response += analysis.message;
        
        return { 
            message: response, 
            isWarning: analysis.status === 'severe' || analysis.status === 'warning' 
        };
    } catch (error) {
        console.error('❌ Error in handleUserLocationQuery:', error);
        return {
            message: '❌ Đã xảy ra lỗi khi phân tích dữ liệu giao thông. Chi tiết lỗi đã được ghi trong console.',
            isWarning: true
        };
    }
}

/**
 * Handle Dak Lak location-specific queries WITH STREET NAMES (Defensive Programming)
 * @param {string} query - User query
 * @returns {Object} Response object
 */
function handleDakLakQuery(query) {
    // Validate that TrafficDataModule exists
    if (!window.TrafficDataModule || !window.TrafficDataModule.analyzeTrafficAtLocation) {
        return {
            message: '⚠️ Mô-đun phân tích giao thông chưa sẵn sàng. Vui lòng tải lại trang.',
            isWarning: true
        };
    }
    
    // Validate that SIMULATED_TRAFFIC_DATA exists
    if (!window.SIMULATED_TRAFFIC_DATA || !window.SIMULATED_TRAFFIC_DATA.dakLakLocation) {
        return {
            message: '⏳ Dữ liệu giao thông đang được tải, vui lòng thử lại sau giây lát.',
            isWarning: false
        };
    }
    
    try {
        const analysis = window.TrafficDataModule.analyzeTrafficAtLocation('dakLakLocation');
        
        console.log('🔍 Dak Lak Analysis:', analysis);
        console.log('📊 Total segments:', analysis.totalSegments);
        console.log('🔴 Severe segments:', analysis.severeSegmentCount);
        console.log('🟠 Moderate segments:', analysis.moderateSegmentCount);
        
        let response = '📍 Tình trạng giao thông tại Số 42 Phạm Hùng, Tân An, Đắk Lắk:\n\n';
        
        if (analysis.status === 'unknown') {
            response += analysis.message;
            return { message: response, isWarning: false };
        }
        
        // Use the detailed message with street names from analyzeTrafficAtLocation
        response += analysis.message;
        
        // Add summary statistics (segment counts match visual map lines)
        response += `\n\n📊 Tổng kết:\n`;
        response += `• Tổng số đoạn đường: ${analysis.totalSegments}\n`;
        response += `• Đoạn tắc nghẽn nghiêm trọng: ${analysis.severeSegmentCount} đoạn\n`;
        response += `• Đoạn ùn ứ vừa phải: ${analysis.moderateSegmentCount} đoạn`;
        
        return { 
            message: response, 
            isWarning: analysis.status === 'severe' || analysis.status === 'warning' 
        };
    } catch (error) {
        console.error('❌ Error in handleDakLakQuery:', error);
        return {
            message: '❌ Đã xảy ra lỗi khi phân tích dữ liệu giao thông. Chi tiết lỗi đã được ghi trong console.',
            isWarning: true
        };
    }
}

/**
 * Handle current traffic status query WITH STREET NAMES (Defensive Programming)
 * @returns {Object} Response object
 */
function handleCurrentTrafficQuery() {
    // Validate that TrafficDataModule exists
    if (!window.TrafficDataModule || !window.TrafficDataModule.analyzeTrafficAtLocation) {
        return {
            message: '⚠️ Mô-đun phân tích giao thông chưa sẵn sàng. Vui lòng tải lại trang.',
            isWarning: true
        };
    }
    
    // Validate that SIMULATED_TRAFFIC_DATA exists
    if (!window.SIMULATED_TRAFFIC_DATA) {
        return {
            message: '⏳ Dữ liệu giao thông đang được tải, vui lòng thử lại sau giây lát.',
            isWarning: false
        };
    }
    
    try {
        const userAnalysis = window.TrafficDataModule.analyzeTrafficAtLocation('userLocation');
        const dakLakAnalysis = window.TrafficDataModule.analyzeTrafficAtLocation('dakLakLocation');
        
        console.log('🔍 Comprehensive Traffic Analysis');
        console.log('User Location:', userAnalysis.status, '- Segments:', userAnalysis.totalSegments);
        console.log('Dak Lak:', dakLakAnalysis.status, '- Segments:', dakLakAnalysis.totalSegments);
        
        let response = '🚦 BÁO CÁO GIAO THÔNG TOÀN DIỆN\n\n';
        
        // User location section
        response += '📍 Khu vực của bạn:\n';
        if (userAnalysis.status !== 'unknown') {
            response += userAnalysis.message + '\n';
        } else {
            response += 'Chưa có dữ liệu.\n';
        }
        
        response += '\n---\n\n';
        
        // Dak Lak section
        response += '📍 Đắk Lắk (Số 42 Phạm Hùng):\n';
        if (dakLakAnalysis.status !== 'unknown') {
            response += dakLakAnalysis.message;
        } else {
            response += 'Chưa có dữ liệu.';
        }
        
        const hasWarning = userAnalysis.status === 'severe' || dakLakAnalysis.status === 'severe';
        
        return { message: response, isWarning: hasWarning };
    } catch (error) {
        console.error('❌ Error in handleCurrentTrafficQuery:', error);
        return {
            message: '❌ Đã xảy ra lỗi khi phân tích dữ liệu giao thông. Chi tiết lỗi đã được ghi trong console.',
            isWarning: true
        };
    }
}

/**
 * Handle traffic violation queries
 * @param {string} query - User query
 * @returns {Object} Response object
 */
function handleTrafficViolationQuery(query) {
    let response = '⚖️ **Mức phạt vi phạm giao thông (Nghị định 100/2019):**\n\n';
    
    if (query.includes('vượt đèn') || query.includes('đèn đỏ')) {
        response += '🚦 **Vượt đèn đỏ:**\n';
        response += '• Xe máy: 4.000.000 - 6.000.000đ\n';
        response += '• Ô tô: 18.000.000 - 20.000.000đ\n';
        response += '• Bị tước GPLX: 1-3 tháng';
    } else if (query.includes('tốc độ') || query.includes('quá tốc')) {
        response += '🏎️ **Vượt quá tốc độ:**\n';
        response += '• Vượt 5-10 km/h: 800.000 - 1.000.000đ\n';
        response += '• Vượt 10-20 km/h: 1.200.000 - 1.500.000đ\n';
        response += '• Vượt trên 20 km/h: 3.000.000 - 5.000.000đ (xe máy)\n';
        response += '• Vượt trên 35 km/h: 16.000.000 - 18.000.000đ (ô tô)';
    } else if (query.includes('rượu') || query.includes('cồn')) {
        response += '🍺 **Vi phạm nồng độ cồn:**\n';
        response += '• Xe máy (< 50mg/100ml): 6.000.000 - 8.000.000đ\n';
        response += '• Xe máy (≥ 50mg/100ml): 30.000.000 - 40.000.000đ\n';
        response += '• Ô tô (< 50mg/100ml): 16.000.000 - 18.000.000đ\n';
        response += '• Ô tô (≥ 50mg/100ml): 30.000.000 - 40.000.000đ\n';
        response += '• Tước GPLX: 22-24 tháng';
    } else {
        response += '📋 **Một số vi phạm phổ biến:**\n';
        response += '• Không đội mũ bảo hiểm: 400.000đ\n';
        response += '• Không có GPLX: 4.000.000 - 6.000.000đ\n';
        response += '• Dùng điện thoại khi lái xe: 600.000 - 800.000đ\n';
        response += '• Không chấp hành hiệu lệnh: 800.000 - 1.000.000đ\n\n';
        response += 'Bạn muốn biết chi tiết về vi phạm nào?';
    }
    
    return { message: response, isWarning: false };
}

/**
 * Handle speed limit queries
 * @param {string} query - User query
 * @returns {Object} Response object
 */
function handleSpeedLimitQuery(query) {
    const response = '🏎️ **Quy định tốc độ tối đa (theo Luật Giao thông):**\n\n' +
                     '**Xe máy:**\n' +
                     '• Trong đô thị: 50 km/h\n' +
                     '• Ngoài đô thị: 60 km/h\n\n' +
                     '**Ô tô con:**\n' +
                     '• Trong đô thị: 60 km/h\n' +
                     '• Ngoài đô thị: 90 km/h\n' +
                     '• Đường cao tốc: 120 km/h\n\n' +
                     '**Ô tô tải, xe khách:**\n' +
                     '• Trong đô thị: 50 km/h\n' +
                     '• Ngoài đô thị: 80 km/h\n' +
                     '• Đường cao tốc: 90 km/h\n\n' +
                     '⚠️ Lưu ý: Có thể giảm tốc độ tùy theo biển báo và điều kiện thời tiết.';
    
    return { message: response, isWarning: false };
}

/**
 * Handle alcohol-related queries
 * @returns {Object} Response object
 */
function handleAlcoholQuery() {
    const response = '🍺 **Quy định về nồng độ cồn (Nghị định 100/2019):**\n\n' +
                     '⛔ **NGHIÊM CẤM** người điều khiển phương tiện có nồng độ cồn > 0 mg/100ml máu hoặc > 0 mg/1 lít khí thở.\n\n' +
                     '**Mức phạt xe máy:**\n' +
                     '• < 50 mg/100ml máu: 6.000.000 - 8.000.000đ\n' +
                     '• ≥ 50 mg/100ml máu: 30.000.000 - 40.000.000đ + tước GPLX 22-24 tháng\n\n' +
                     '**Mức phạt ô tô:**\n' +
                     '• < 50 mg/100ml máu: 16.000.000 - 18.000.000đ\n' +
                     '• 50-80 mg/100ml máu: 30.000.000 - 40.000.000đ + tước GPLX 22-24 tháng\n' +
                     '• ≥ 80 mg/100ml máu: 30.000.000 - 40.000.000đ + tước GPLX 22-24 tháng\n\n' +
                     '🚨 **Khuyến nghị:** Không lái xe sau khi uống rượu bia!';
    
    return { message: response, isWarning: true };
}

/**
 * Handle helmet queries
 * @returns {Object} Response object
 */
function handleHelmetQuery() {
    const response = '🪖 **Quy định về mũ bảo hiểm:**\n\n' +
                     '✅ **Bắt buộc:**\n' +
                     '• Người điều khiển và người ngồi sau xe máy, xe gắn máy phải đội mũ bảo hiểm đạt chuẩn.\n' +
                     '• Trẻ em dưới 6 tuổi ngồi sau phải có người lớn bảo vệ.\n\n' +
                     '**Mức phạt không đội mũ bảo hiểm:**\n' +
                     '• 400.000đ (người điều khiển)\n' +
                     '• 200.000đ (người ngồi sau)\n\n' +
                     '**Tiêu chuẩn mũ bảo hiểm:**\n' +
                     '• Có dấu hợp chuẩn theo quy chuẩn kỹ thuật quốc gia\n' +
                     '• Kích thước phù hợp với đầu người đội\n' +
                     '• Dây đeo cài chặt dưới cằm';
    
    return { message: response, isWarning: false };
}

/**
 * Handle red light queries
 * @returns {Object} Response object
 */
function handleRedLightQuery() {
    const response = '🚦 **Quy định về đèn tín hiệu giao thông:**\n\n' +
                     '**Ý nghĩa:**\n' +
                     '• 🔴 Đèn đỏ: Phải dừng lại\n' +
                     '• 🟡 Đèn vàng: Giảm tốc độ, chuẩn bị dừng (trừ khi đã quá gần)\n' +
                     '• 🟢 Đèn xanh: Được đi nhưng phải quan sát\n\n' +
                     '**Mức phạt vượt đèn đỏ:**\n' +
                     '• Xe máy: 4.000.000 - 6.000.000đ + tước GPLX 1-3 tháng\n' +
                     '• Ô tô: 18.000.000 - 20.000.000đ + tước GPLX 1-3 tháng\n\n' +
                     '⚠️ **Lưu ý:** Camera giám sát giao thông sẽ ghi hình vi phạm.';
    
    return { message: response, isWarning: true };
}

/**
 * Handle license queries
 * @returns {Object} Response object
 */
function handleLicenseQuery() {
    const response = '📜 **Giấy phép lái xe (GPLX):**\n\n' +
                     '**Hạng GPLX theo loại xe:**\n' +
                     '• A1: Xe máy dung tích < 175cm³\n' +
                     '• A2: Xe máy dung tích ≥ 175cm³\n' +
                     '• B1: Ô tô ≤ 9 chỗ ngồi (số tự động)\n' +
                     '• B2: Ô tô ≤ 9 chỗ ngồi (số sàn)\n' +
                     '• C, D, E, F: Xe tải, xe khách...\n\n' +
                     '**Mức phạt không có GPLX:**\n' +
                     '• Xe máy: 4.000.000 - 6.000.000đ + tạm giữ xe\n' +
                     '• Ô tô: 18.000.000 - 20.000.000đ + tạm giữ xe\n\n' +
                     '**Mức phạt GPLX không phù hợp:**\n' +
                     '• 4.000.000 - 6.000.000đ + tước GPLX 2-4 tháng\n\n' +
                     '⚠️ Phải mang theo GPLX khi tham gia giao thông!';
    
    return { message: response, isWarning: false };
}

/**
 * Handle chat form submission
 * @param {Event} e - Form submit event
 */
async function handleChatSubmit(e) {
    e.preventDefault();
    
    if (isProcessing) return;
    
    const input = document.getElementById('chat-input');
    const query = input.value.trim();
    
    if (!query) return;
    
    // Add user message
    addUserMessage(query);
    input.value = '';
    
    // Show typing indicator
    isProcessing = true;
    showTypingIndicator();
    
    try {
        // Process query
        const response = await processQuery(query);
        
        // Hide typing indicator
        hideTypingIndicator();
        
        // Add bot response
        addBotMessage(response.message, response.isWarning);
    } catch (error) {
        hideTypingIndicator();
        addBotMessage('❌ Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại.', false);
    } finally {
        isProcessing = false;
    }
}

/**
 * Initialize chatbot event listeners
 * CRITICAL: Uses capture phase to run BEFORE Nuclear Prevention script
 */
function setupChatbot() {
    const form = document.getElementById('chat-form');
    if (form) {
        // Use capture phase (true) to ensure this runs first
        form.addEventListener('submit', handleChatSubmit, true);
        console.log('✅ Chatbot event listener attached (capture phase)');
    } else {
        console.warn('⚠️ Chat form not found, retrying in 500ms...');
        setTimeout(setupChatbot, 500);
    }
}

// Setup when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupChatbot);
} else {
    setupChatbot();
}

// Export for global access
window.ChatbotModule = {
    initializeChatbot,
    handleChatSubmit
};
