/**
 * Main Application Logic
 * Handles UI interactions, tab switching, charts, and map initialization
 */

// Global configuration
const CONFIG = {
    CENTER_LAT: 21.028511, // Default: Hanoi
    CENTER_LNG: 105.804817,
    ZOOM_LEVEL: 13,
    NUM_DATA_POINTS: 25
};

// Global state
let maps = {};
let charts = {};

// Community posts data
let postsData = [
    {
        id: 'USER-A1B2C3D4',
        location: 'Đường vành đai 3',
        content: 'Tình trạng kẹt xe nghiêm trọng do va chạm. Tránh khu vực này!',
        image: 'https://images2.thanhnien.vn/528068263637045248/2024/3/4/43-tai-nan-1-1709521762276696450071.jpg',
        timestamp: '2025-10-25T10:00:00Z',
        comments: [{ userId: 'USER-X1Y2', text: 'Cảm ơn bác tài!' }]
    },
    {
        id: 'USER-E5F6G7H8',
        location: 'Cầu Sài Gòn',
        content: 'Mưa lớn đường trơn, đi chậm nhé mọi người.',
        image: 'https://vcdn1-vnexpress.vnecdn.net/2024/05/08/z5421316128313-505bd543281528f-7841-3603-1715168354.jpg?w=460&h=0&q=100&dpr=2&fit=crop&s=oRJHNNL1pyXHRAyjRWNn5A',
        timestamp: '2025-10-25T09:30:00Z',
        comments: []
    }
];

/**
 * Initialize Leaflet map
 * @param {string} mapId - DOM element ID for the map
 * @returns {Object} Leaflet map instance
 */
function initializeMap(mapId) {
    if (maps[mapId]) maps[mapId].remove();
    
    const map = L.map(mapId).setView([CONFIG.CENTER_LAT, CONFIG.CENTER_LNG], CONFIG.ZOOM_LEVEL);
    maps[mapId] = map;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    setTimeout(() => map.invalidateSize(), 100);
    return map;
}

/**
 * Add user location marker to map
 * @param {Object} map - Leaflet map instance
 * @param {Function} onLocationFound - Callback when location is obtained
 */
function addUserLocation(map, onLocationFound) {
    // TODO: Uncomment the GPS block below to re-enable geolocation
    // if (navigator.geolocation) {
    //     navigator.geolocation.getCurrentPosition(
    //         (pos) => {
    //             const lat = pos.coords.latitude;
    //             const lng = pos.coords.longitude;

    //             // User location marker
    //             const userIcon = L.divIcon({
    //                 className: 'custom-div-icon',
    //                 html: "<div style='background-color:#1D4ED8;width:15px;height:15px;border-radius:50%;border:2px solid white;box-shadow:0 0 5px rgba(0,0,0,0.5);'></div>",
    //                 iconSize: [15, 15],
    //                 iconAnchor: [7, 7]
    //             });

    //             L.marker([lat, lng], { icon: userIcon })
    //                 .addTo(map)
    //                 .bindPopup('<div class="text-center font-bold text-primary-blue">📍 Vị trí của bạn</div>')
    //                 .openPopup();
                
    //             map.setView([lat, lng], 14);

    //             if (onLocationFound) onLocationFound(lat, lng);
    //         },
    //         (error) => {
    //             console.log("GPS Error: " + error.message);
    //             if (onLocationFound) onLocationFound(CONFIG.CENTER_LAT, CONFIG.CENTER_LNG);
    //         }
    //     );
    // } else {
    //     if (onLocationFound) onLocationFound(CONFIG.CENTER_LAT, CONFIG.CENTER_LNG);
    // }

    // ===== GPS DISABLED: Using Default Location =====
    console.log("📍 GPS is disabled. Using default location (Dak Lak).");
    
    // Default coordinates (Dak Lak, Vietnam)
    const defaultLat = 12.6976;
    const defaultLng = 108.0674;

    // Create user location marker (same styling as GPS version)
    const userIcon = L.divIcon({
        className: 'custom-div-icon',
        html: "<div style='background-color:#1D4ED8;width:15px;height:15px;border-radius:50%;border:2px solid white;box-shadow:0 0 5px rgba(0,0,0,0.5);'></div>",
        iconSize: [15, 15],
        iconAnchor: [7, 7]
    });

    L.marker([defaultLat, defaultLng], { icon: userIcon })
        .addTo(map)
        .bindPopup('<div class="text-center font-bold text-primary-blue">📍 Vị trí mặc định (Dak Lak)</div>')
        .openPopup();
    
    // Center map on default location
    map.setView([defaultLat, defaultLng], 14);

    // Trigger callback with default coordinates
    if (onLocationFound) onLocationFound(defaultLat, defaultLng);
}

/**
 * Generate scattered data points for visualization
 * @param {number} centerLat - Center latitude
 * @param {number} centerLng - Center longitude
 * @param {number} numPoints - Number of points to generate
 * @param {Object} statusMap - Status configuration map
 * @returns {Array} Generated data points
 */
function generateScatteredData(centerLat, centerLng, numPoints, statusMap) {
    const data = [];
    for (let i = 0; i < numPoints; i++) {
        const lat = centerLat + (Math.random() - 0.5) * 0.06;
        const lng = centerLng + (Math.random() - 0.5) * 0.06;
        const statuses = Object.keys(statusMap);
        const randomStatus = statuses[Math.floor(Math.random() * statuses.length)];
        data.push({ 
            lat, 
            lng, 
            status: randomStatus, 
            value: statusMap[randomStatus].value 
        });
    }
    return data;
}

/**
 * Draw data points on map
 * @param {Object} map - Leaflet map instance
 * @param {Array} data - Data points to draw
 * @param {Object} statusMap - Status configuration
 * @param {string} popupTitle - Title for popup
 */
function drawDataPoints(map, data, statusMap, popupTitle) {
    data.forEach(point => {
        const config = statusMap[point.status];
        L.circleMarker([point.lat, point.lng], {
            radius: 8,
            fillColor: config.color,
            color: config.color,
            weight: 1,
            opacity: 1,
            fillOpacity: 0.7
        }).addTo(map).bindPopup(`<b>${popupTitle}</b><br>Trạng thái: ${config.label}`);
    });
}

/**
 * Tab switching logic
 * @param {string} tabId - Tab identifier
 */
function showTab(tabId) {
    // Hide all tab content
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active-tab-content'));
    
    // Reset all tab buttons
    document.querySelectorAll('.tab-button').forEach(b => {
        b.classList.remove('border-primary-blue', 'text-primary-blue');
        b.classList.add('border-transparent', 'text-gray-600');
    });

    // Show selected tab
    document.getElementById(`content-${tabId}`).classList.add('active-tab-content');
    document.getElementById(`tab-${tabId}`).classList.add('border-primary-blue', 'text-primary-blue');
    document.getElementById(`tab-${tabId}`).classList.remove('border-transparent', 'text-gray-600');

    // Handle tab-specific logic
    if (tabId === 'overview') {
        handleOverviewCharts();
    } else if (tabId === 'density') {
        handleTrafficDensityMap();
    } else if (tabId === 'air-quality') {
        handleAirQualityMap();
    }
}

/**
 * Handle Traffic Density Map tab
 * Uses TrafficDataModule to fetch real traffic roads
 */
function handleTrafficDensityMap() {
    const map = initializeMap('map-density');
    
    addUserLocation(map, (lat, lng) => {
        // Generate traffic data for both user location and Dak Lak
        if (window.TrafficDataModule && window.TrafficDataModule.generateDualLocationTrafficData) {
            window.TrafficDataModule.generateDualLocationTrafficData(map, lat, lng);
        }
    });
}

/**
 * Handle Air Quality Map tab
 * Continues using scattered data points for AQI
 */
function handleAirQualityMap() {
    const map = initializeMap('map-air-quality');
    const airStatusMap = {
        unhealthy: { color: '#EF4444', label: 'Kém', value: 'AQI 125' },
        moderate: { color: '#FBBF24', label: 'Trung bình', value: 'AQI 78' },
        good: { color: '#10B981', label: 'Tốt', value: 'AQI 35' }
    };

    addUserLocation(map, (lat, lng) => {
        const airData = generateScatteredData(lat, lng, CONFIG.NUM_DATA_POINTS, airStatusMap);
        drawDataPoints(map, airData, airStatusMap, 'Trạm đo AQI');
    });
}

/**
 * Get chart labels (last 6 hours)
 * @returns {Array} Hour labels
 */
function getChartLabels() {
    const labels = [];
    const now = new Date();
    now.setHours(15, 0, 0, 0);
    for (let i = 5; i >= 0; i--) {
        const hour = (now.getHours() - i + 24) % 24;
        labels.push(`${hour}:00`);
    }
    return labels;
}

/**
 * Create line chart
 * @param {string} id - Canvas element ID
 * @param {string} instanceName - Chart instance name
 * @param {Array} labels - X-axis labels
 * @param {Array} data - Chart data
 * @param {Object} config - Chart configuration
 */
function createLineChart(id, instanceName, labels, data, config) {
    if (charts[instanceName]) charts[instanceName].destroy();
    
    const ctx = document.getElementById(id).getContext('2d');
    charts[instanceName] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: config.label,
                data: data,
                borderColor: config.borderColor,
                backgroundColor: config.backgroundColor,
                borderWidth: 3,
                pointRadius: 4,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { 
                    beginAtZero: false, 
                    grid: { color: '#E5E7EB' } 
                },
                x: { 
                    grid: { display: false } 
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

/**
 * Handle Overview tab charts
 */
function handleOverviewCharts() {
    const labels = getChartLabels();
    
    // Update stats
    document.getElementById('stat-congestion').textContent = '2.8 km';
    document.getElementById('stat-air-quality').textContent = '112 AQI';
    document.getElementById('stat-incidents').textContent = '4';

    // Create charts
    createLineChart('chart-congestion', 'congestion', labels, [1.5, 1.8, 2.0, 1.9, 2.4, 2.8], {
        label: 'Tắc nghẽn (km)',
        borderColor: '#1D4ED8',
        backgroundColor: 'rgba(29, 78, 216, 0.1)'
    });

    createLineChart('chart-air-quality', 'air', labels, [90, 95, 105, 118, 115, 112], {
        label: 'AQI',
        borderColor: '#16A34A',
        backgroundColor: 'rgba(22, 163, 74, 0.1)'
    });

    createLineChart('chart-incidents', 'incidents', labels, [1, 1, 2, 3, 2, 4], {
        label: 'Sự cố',
        borderColor: '#DC2626',
        backgroundColor: 'rgba(220, 38, 38, 0.1)'
    });
}

/**
 * Render community posts
 * @param {Array} posts - Posts data
 */
function renderPosts(posts) {
    const container = document.getElementById('community-feed');
    if (!container) return;
    
    posts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    container.innerHTML = posts.map(post => {
        const timeAgo = formatTimeAgo(new Date(post.timestamp));
        return `
        <div class="bg-gray-50 p-4 rounded-xl shadow-inner border border-gray-200">
            <div class="flex items-start mb-3 space-x-3">
                <div class="w-10 h-10 bg-primary-blue rounded-full flex items-center justify-center text-white font-bold text-sm">ID</div>
                <div>
                    <p class="font-bold text-gray-800 text-sm">${post.id.split('-')[0]}***</p>
                    <p class="text-xs text-gray-500">${timeAgo}</p>
                </div>
            </div>
            <p class="text-sm font-medium text-gray-600 mb-2">📍 ${post.location}</p>
            <p class="text-gray-700 mb-3">${post.content}</p>
            ${post.image ? `<img src="${post.image}" class="w-full h-48 object-cover rounded-lg mb-3 shadow-sm" onerror="this.style.display='none'">` : ''}
        </div>`;
    }).join('');
}

/**
 * Handle new post submission with image upload support
 * @param {Event} e - Form submit event
 */
function handleNewPost(e) {
    e.preventDefault();
    
    const content = document.getElementById('post-content').value.trim();
    const location = document.getElementById('post-location').value.trim();
    const imageInput = document.getElementById('post-image');
    const statusDiv = document.getElementById('post-status');
    
    if (!content) return;
    
    statusDiv.textContent = 'Đang đăng...';
    statusDiv.classList.remove('hidden');
    statusDiv.classList.add('text-blue-600');
    
    // Check if user selected an image
    const file = imageInput.files[0];
    
    if (file) {
        // Use FileReader to convert image to Base64
        const reader = new FileReader();
        
        reader.onload = function(event) {
            // Create post with Base64 image
            createPost(content, location, event.target.result, statusDiv, e.target);
        };
        
        reader.onerror = function() {
            console.error('Error reading file');
            // Create post without image if reading fails
            createPost(content, location, null, statusDiv, e.target);
        };
        
        reader.readAsDataURL(file);
    } else {
        // No image selected, create post immediately
        createPost(content, location, null, statusDiv, e.target);
    }
}

/**
 * Create and add new post to feed
 * @param {string} content - Post content
 * @param {string} location - Post location
 * @param {string} imageData - Base64 image data or null
 * @param {HTMLElement} statusDiv - Status display element
 * @param {HTMLElement} form - Form element to reset
 */
function createPost(content, location, imageData, statusDiv, form) {
    setTimeout(() => {
        const newPost = {
            id: 'USER-' + Math.random().toString(36).substr(2, 5).toUpperCase(),
            location: location || 'Không xác định',
            content: content,
            timestamp: new Date().toISOString(),
            comments: []
        };
        
        // Add image if provided
        if (imageData) {
            newPost.image = imageData;
        }
        
        postsData.unshift(newPost);
        
        renderPosts(postsData);
        form.reset();
        
        statusDiv.textContent = '✅ Đăng thành công!';
        statusDiv.classList.remove('text-blue-600');
        statusDiv.classList.add('text-green-600');
        
        setTimeout(() => {
            statusDiv.classList.add('hidden');
            showTab('posts');
        }, 1000);
    }, 800);
}

/**
 * Format time ago (simplified)
 * @param {Date} date - Date object
 * @returns {string} Formatted time string
 */
function formatTimeAgo(date) {
    return "Vừa xong";
}

/**
 * Initialize application
 */
window.onload = function() {
    renderPosts(postsData);
    showTab('overview');
    
    // Setup form submission
    const form = document.getElementById('new-post-form');
    if (form) {
        form.addEventListener('submit', handleNewPost);
    }
    
    // Video analysis is now initialized inline in HTML (nuclear mode)
    console.log('✅ Main app initialization complete');
};

/**
 * Toggle chat widget visibility (mutually exclusive with FAB)
 */
function toggleChatWidget() {
    const popup = document.getElementById('chat-popup');
    const fab = document.getElementById('chat-fab');
    
    if (popup && fab) {
        const isHidden = popup.classList.contains('hidden');
        
        if (isHidden) {
            // Open chat: Show popup, hide FAB
            popup.classList.remove('hidden');
            fab.classList.add('hidden');
            
            // Initialize chatbot on first open
            if (window.ChatbotModule && window.ChatbotModule.initializeChatbot) {
                window.ChatbotModule.initializeChatbot();
            }
        } else {
            // Close chat: Hide popup, show FAB
            popup.classList.add('hidden');
            fab.classList.remove('hidden');
        }
    }
}

/**
 * Unified Media Analysis Function - NUCLEAR VERSION
 * Handles both image and video upload with AI models
 * MAXIMUM prevention against page reloads
 */
async function handleMediaAnalysis(e) {
    // ============================================================
    // NUCLEAR OPTION: Prevent EVERYTHING that could cause reload
    // ============================================================
    if (e) {
        try {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
        } catch (err) {
            console.warn('Event prevention error:', err);
        }
    }
    
    console.log('🤖 handleMediaAnalysis called - NO PAGE RELOAD!');
    
    const mediaInput = document.getElementById('media-input');
    const analyzeButton = document.getElementById('analyze-button');
    const loadingSpinner = document.getElementById('loading-spinner');
    const mediaResultContainer = document.getElementById('media-result-container');
    const errorMessage = document.getElementById('error-message');
    
    // Validate file selection
    if (!mediaInput.files || mediaInput.files.length === 0) {
        console.warn('⚠️ No file selected');
        showError('Vui lòng chọn một ảnh hoặc video để phân tích!');
        return;
    }
    
    const mediaFile = mediaInput.files[0];
    console.log('📁 File selected:', mediaFile.name, 'Type:', mediaFile.type, 'Size:', mediaFile.size);
    
    // Detect media type
    const isImage = mediaFile.type.startsWith('image/');
    const isVideo = mediaFile.type.startsWith('video/');
    
    if (!isImage && !isVideo) {
        console.warn('⚠️ Invalid file type:', mediaFile.type);
        showError('File được chọn không phải là ảnh hoặc video. Vui lòng chọn file hợp lệ!');
        return;
    }
    
    const mediaType = isImage ? 'image' : 'video';
    console.log(`📸 Media type detected: ${mediaType}`);
    
    // Reset UI - Hide previous results and errors
    console.log('🔄 Resetting UI...');
    errorMessage.classList.add('hidden');
    mediaResultContainer.classList.add('hidden');
    loadingSpinner.classList.remove('hidden');
    analyzeButton.disabled = true;
    analyzeButton.textContent = 'Đang xử lý...';
    console.log('⏳ Loading spinner shown, button disabled');
    
    try {
        // Prepare form data
        console.log('📦 Preparing form data...');
        const formData = new FormData();
        formData.append(mediaType, mediaFile);
        
        // Determine endpoint based on media type
        const endpoint = isImage ? 'http://localhost:5000/analyze_image' : 'http://localhost:5000/analyze_video';
        console.log(`🚀 Sending request to: ${endpoint}`);
        
        // Send request to backend
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });
        
        console.log('📥 Response received. Status:', response.status);
        const data = await response.json();
        console.log('📊 Response data:', data);
        
        if (!response.ok) {
            console.error('❌ Server error:', response.status);
            throw new Error(data.error || `Lỗi khi xử lý ${mediaType}`);
        }
        
        if (data.success) {
            console.log('✅ Analysis successful! Displaying results...');
            
            // Media URL is ABSOLUTE pointing to Flask server (port 5000)
            const mediaUrl = data.media_url || data.video_url || data.image_url;
            console.log('📹 Raw media URL from server:', mediaUrl);
            
            // CRITICAL: Add cache-busting timestamp
            const timestamp = data.timestamp || new Date().getTime();
            const mediaUrlWithCacheBuster = mediaUrl.includes('?') 
                ? `${mediaUrl}&t=${timestamp}`
                : `${mediaUrl}?t=${timestamp}`;
            
            console.log('🎬 Final media URL (with cache buster):', mediaUrlWithCacheBuster);
            console.log('🌐 Media will be loaded from Flask server (port 5000)');
            
            // Update data object with cache-busted URL and media type
            data.media_url = mediaUrlWithCacheBuster;
            data.media_type = mediaType;
            
            // Display results inline
            displayMediaResults(data);
        } else {
            console.error('❌ Analysis failed:', data.error);
            throw new Error(data.error || `Không thể phân tích ${mediaType}`);
        }
        
    } catch (error) {
        console.error('💥 Error analyzing media:', error);
        
        // Detailed error message
        let errorMsg = `Lỗi: ${error.message}`;
        if (error.message.includes('Failed to fetch')) {
            errorMsg += '\n\n🔴 Server không phản hồi. Vui lòng kiểm tra:\n1. Server đang chạy? (python server.py)\n2. Port 5000 có bị chặn?\n3. CORS có được cấu hình?';
        }
        
        showError(errorMsg);
    } finally {
        // Reset UI
        console.log('🔄 Resetting button state...');
        loadingSpinner.classList.add('hidden');
        analyzeButton.disabled = false;
        analyzeButton.textContent = '🔍 Phân Tích';
        console.log('✅ Button re-enabled');
    }
    
    // NUCLEAR: Ensure we didn't accidentally reload
    console.log('✅ handleMediaAnalysis completed WITHOUT page reload!');
    return false;
}

/**
 * Legacy function - kept for backward compatibility
 */
async function handleVideoAnalysis(e) {
    return handleMediaAnalysis(e);
}

/**
 * Display unified media analysis results inline below the button
 */
function displayMediaResults(data) {
    console.log('📊 displayMediaResults called with data:', data);
    
    const mediaResultContainer = document.getElementById('media-result-container');
    const trafficStatus = document.getElementById('result-traffic-status');
    const vehicleCount = document.getElementById('result-vehicle-count');
    const accidentWarning = document.getElementById('result-accident-warning');
    const accidentCard = document.getElementById('accident-card');
    const mediaStatusText = document.getElementById('media-status-text');
    
    // Get media containers
    const imageContainer = document.getElementById('image-container');
    const videoContainer = document.getElementById('video-container');
    const processedImage = document.getElementById('processed-image');
    const processedVideoPlayer = document.getElementById('processed-video-player');
    
    const mediaType = data.media_type || 'video';
    const mediaUrl = data.media_url;
    
    console.log(`📹 Setting ${mediaType} source:`, mediaUrl);
    
    // Update traffic status
    trafficStatus.textContent = data.traffic_status;
    
    // Update vehicle count
    vehicleCount.textContent = data.vehicle_count;
    
    // Update accident warning
    const hasAccident = data.accident_warning;
    accidentWarning.textContent = hasAccident ? '⚠️ CÓ' : '✅ KHÔNG';
    
    // Style accident card based on warning
    if (hasAccident) {
        accidentCard.className = 'bg-gradient-to-br from-red-500 to-red-600 text-white p-4 rounded-lg shadow-md';
    } else {
        accidentCard.className = 'bg-gradient-to-br from-gray-400 to-gray-500 text-white p-4 rounded-lg shadow-md';
    }
    
    // Update status text
    const accidentText = hasAccident ? '⚠️ PHÁT HIỆN TAI NẠN' : '✅ Không phát hiện tai nạn';
    mediaStatusText.textContent = `Trạng thái: ${data.traffic_status} | Phương tiện: ${data.vehicle_count} | ${accidentText}`;
    mediaStatusText.className = hasAccident 
        ? 'mt-2 mb-4 text-base font-bold text-red-600' 
        : 'mt-2 mb-4 text-base font-bold text-green-600';
    
    // Show appropriate media container based on type
    if (mediaType === 'image') {
        console.log('🖼️ Displaying image result');
        videoContainer.classList.add('hidden');
        imageContainer.classList.remove('hidden');
        
        // Load image
        processedImage.src = mediaUrl;
        processedImage.alt = 'Processed Traffic Image';
        processedImage.className = 'w-full rounded-lg shadow-lg';
        
    } else {
        console.log('📹 Displaying video result');
        imageContainer.classList.add('hidden');
        videoContainer.classList.remove('hidden');
        
        // CRITICAL: Clear any existing video source first to prevent caching
        processedVideoPlayer.src = '';
        processedVideoPlayer.load();
        
        // Load and display processed video with cache busting
        console.log('📹 Loading video into player with URL:', mediaUrl);
        
        // Remove any existing event listeners by cloning the element
        const newVideoPlayer = processedVideoPlayer.cloneNode(true);
        processedVideoPlayer.parentNode.replaceChild(newVideoPlayer, processedVideoPlayer);
        
        // Get error message element for auto-hide on success
        const errorMessage = document.getElementById('error-message');
        
        // Add comprehensive event listeners for debugging
        newVideoPlayer.addEventListener('loadstart', function() {
            console.log('📹 Video loading started');
        });
        
        newVideoPlayer.addEventListener('loadedmetadata', function() {
            console.log('📹 Video metadata loaded. Duration:', this.duration, 'seconds');
        });
        
        newVideoPlayer.addEventListener('canplay', function() {
            console.log('✅ Video ready to play');
        });
        
        // SUCCESS HANDLER: Auto-hide error when video actually loads
        newVideoPlayer.addEventListener('loadeddata', function() {
            console.log('✅ Video loaded successfully! Hiding any error messages.');
            if (errorMessage) {
                errorMessage.classList.add('hidden');
                const errorText = document.getElementById('error-text');
                if (errorText) {
                    errorText.textContent = '';
                }
            }
            console.log('🎉 Video recovered successfully - error banner hidden');
        });
        
        // ERROR HANDLER: Only show persistent errors (debounced)
        let errorTimeout = null;
        newVideoPlayer.addEventListener('error', function(e) {
            console.warn('⚠️ Video playback hiccup detected (debouncing...)');
            
            // Clear any existing timeout
            if (errorTimeout) {
                clearTimeout(errorTimeout);
            }
            
            // Wait 500ms before showing error (gives browser time to recover)
            errorTimeout = setTimeout(() => {
                console.error('❌ Video load error persisted after 500ms');
                console.error('Error code:', this.error ? this.error.code : 'unknown');
                console.error('Error message:', this.error ? this.error.message : 'unknown');
                console.error('Video src:', this.src);
                console.error('Current time:', this.currentTime);
                console.error('Network state:', this.networkState);
                console.error('Ready state:', this.readyState);
                
                // Error code meanings:
                // 1 = MEDIA_ERR_ABORTED - User aborted
                // 2 = MEDIA_ERR_NETWORK - Network error
                // 3 = MEDIA_ERR_DECODE - Decode error
                // 4 = MEDIA_ERR_SRC_NOT_SUPPORTED - Format not supported
                
                let errorDetail = '';
                if (this.error) {
                    switch(this.error.code) {
                        case 1:
                            errorDetail = 'User aborted video loading';
                            break;
                        case 2:
                            errorDetail = 'Network error - Cannot reach Flask server (port 5000)';
                            break;
                        case 3:
                            errorDetail = 'Video decode error - File may be corrupted';
                            break;
                        case 4:
                            errorDetail = 'Video format not supported by browser';
                            break;
                        default:
                            errorDetail = 'Unknown error';
                    }
                }
                
                console.error('❌ Error detail:', errorDetail);
                console.error('🔍 Check: Is Flask server (python server.py) running on port 5000?');
                
                // Show user-friendly error only if truly fatal
                showError(`❌ Không thể tải video!\n\n${errorDetail}\n\nVui lòng kiểm tra:\n1. Flask server đang chạy? (python server.py)\n2. Port 5000 không bị chặn?\n3. File video tồn tại?\n\nURL: ${this.src}`);
            }, 500);
        });
        
        // Set video source with cache buster
        newVideoPlayer.src = mediaUrl;
        newVideoPlayer.load();
    }
    
    // CRITICAL: Explicitly remove 'hidden' class
    console.log('👁️ Showing results container');
    mediaResultContainer.classList.remove('hidden');
    
    // Verify it's actually visible
    const isVisible = !mediaResultContainer.classList.contains('hidden');
    console.log('📊 Results container visible:', isVisible);
    
    if (!isVisible) {
        console.error('⚠️ Results container still hidden! Force removing...');
        mediaResultContainer.style.display = 'block';
    }
    
    // Smooth scroll to results with slight delay
    setTimeout(() => {
        mediaResultContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        console.log('✅ Results displayed and scrolled into view');
        if (mediaType === 'video') {
            console.log('📍 Video player src:', document.getElementById('processed-video-player').src);
        } else {
            console.log('📍 Image src:', processedImage.src);
        }
    }, 150);
}

/**
 * Legacy function - kept for backward compatibility
 */
function displayVideoResults(data) {
    data.media_type = 'video';
    return displayMediaResults(data);
}

/**
 * Show error message
 */
function showError(message) {
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    
    errorText.textContent = message;
    errorMessage.classList.remove('hidden');
    
    // Hide after 5 seconds
    setTimeout(() => {
        errorMessage.classList.add('hidden');
    }, 5000);
}

/**
 * Initialize Video Analysis button event listener
 * NOTE: This is now handled inline in HTML (nuclear mode)
 * Keeping this function for backward compatibility
 */
function initVideoAnalysis() {
    console.log('⚠️ initVideoAnalysis called (but nuclear mode in HTML takes priority)');
}

// ============================================================
// EXPORT EVERYTHING TO WINDOW FOR NUCLEAR MODE
// ============================================================
window.showTab = showTab;
window.toggleChatWidget = toggleChatWidget;
window.handleVideoAnalysis = handleVideoAnalysis;
window.displayVideoResults = displayVideoResults;
window.showError = showError;

console.log('✅ All functions exported to window object');
console.log('✅ handleVideoAnalysis available:', typeof window.handleVideoAnalysis);

