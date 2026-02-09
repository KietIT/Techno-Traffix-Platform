/**
 * Traffic Data Module
 * Handles OSRM API calls and Traffic Simulation Logic
 * Generates traffic data for both user location and hardcoded Dak Lak location
 */

// Global traffic data storage for chatbot access (PERSISTENT)
window.SIMULATED_TRAFFIC_DATA = {
    userLocation: { lat: null, lng: null, segments: [], loaded: false },
    dakLakLocation: { lat: 12.6976, lng: 108.0674, segments: [], loaded: false },
    lastUpdated: null
};

// Legacy alias for backward compatibility
window.globalTrafficData = window.SIMULATED_TRAFFIC_DATA;

/**
 * Fetch real traffic roads using local backend (CORS-safe, Chatbot-aware)
 * Backend calls OSRM API and returns route geometries with street names
 * @param {Object} map - Leaflet map instance
 * @param {number} centerLat - Center latitude
 * @param {number} centerLng - Center longitude
 * @param {string} locationKey - Key to store data ('userLocation' or 'dakLakLocation')
 */
async function fetchRealTrafficRoads(map, centerLat, centerLng, locationKey = 'userLocation') {
    // Skip if already loaded (persistence)
    if (window.SIMULATED_TRAFFIC_DATA[locationKey].loaded) {
        console.log(`📌 Using cached traffic data for ${locationKey}`);
        redrawExistingSegments(map, locationKey);
        return;
    }
    
    console.log(`🚗 Fetching traffic data from backend for ${locationKey} at (${centerLat}, ${centerLng})`);
    updateTrafficStatus('⏳ Đang tải dữ liệu...');
    
    const segments = [];
    
    try {
        // Call local backend proxy (bypasses CORS, prevents map freezing)
        const backendUrl = `http://localhost:5000/get_traffic_data?lat=${centerLat}&lng=${centerLng}`;
        
        console.log(`🔄 Requesting routes from backend...`);
        const response = await fetch(backendUrl, {
            signal: AbortSignal.timeout(25000) // 25 second timeout
        });
        
        if (!response.ok) {
            throw new Error(`Backend HTTP ${response.status}: ${response.statusText}`);
        }
        
        const trafficData = await response.json();
        
        if (Array.isArray(trafficData) && trafficData.length > 0) {
            console.log(`✅ Received ${trafficData.length} routes from backend`);
            
            // Draw 5km radius circle (simulation area)
            const circleLabel = locationKey === 'userLocation' ? 'Vị trí của bạn' : 'Đắk Lắk';
            L.circle([centerLat, centerLng], {
                color: '#3B82F6',
                fillColor: '#3B82F6',
                fillOpacity: 0.1,
                radius: 5000, // 5km radius
                weight: 2,
                dashArray: '5, 10'
            }).addTo(map).bindPopup(`<div class="text-center font-semibold text-blue-600">🔵 Vùng mô phỏng giao thông<br/><small>Bán kính 5km (${circleLabel})</small></div>`);
            
            // Iterate through routes and draw on map
            trafficData.forEach((route, index) => {
                const color = route.severity === 'severe' ? '#DC2626' : '#F59E0B';
                const weight = route.severity === 'severe' ? 7 : 5;
                const statusText = route.severity === 'severe' 
                    ? 'Tắc nghẽn nghiêm trọng' 
                    : 'Ùn ứ vừa phải';
                
                const polylineOptions = {
                    color: color,
                    weight: weight,
                    opacity: route.isFallback ? 0.8 : 1.0,
                    lineCap: 'round',
                    lineJoin: 'round'
                };
                
                // Add dashed pattern for fallback routes
                if (route.isFallback) {
                    polylineOptions.dashArray = '5, 5';
                }

                L.polyline(route.coordinates, polylineOptions).addTo(map).bindPopup(
                    `<b>⚠️ ${statusText}</b><br>` +
                    `<strong>Đường:</strong> ${route.name}<br>` +
                    `<strong>Độ dài:</strong> ${route.isFallback ? '~' : ''}${(route.distance / 1000).toFixed(2)} km` +
                    (route.isFallback ? '<br><small>(Ước tính - OSRM API không khả dụng)</small>' : '')
                );

                // Store segment for CHATBOT CONTEXT
                segments.push({
                    path: route.coordinates,
                    severity: route.severity,
                    streetName: route.name, // Critical for chatbot "Which roads are congested?"
                    distance: route.distance,
                    duration: route.duration,
                    centerDistance: calculateDistance(centerLat, centerLng, route.coordinates[0][0], route.coordinates[0][1]),
                    isFallback: route.isFallback || false
                });
                
                console.log(`✅ Rendered route ${index + 1}: ${route.name} (${route.severity})`);
            });
            
            console.log(`✅ Successfully rendered ${segments.length} traffic routes`);
            
        } else {
            throw new Error('Backend returned empty or invalid data');
        }
        
    } catch (err) {
        console.error(`❌ Backend request failed: ${err.message}`);
        console.warn(`⚠️ Using emergency fallback mode...`);
        updateTrafficStatus('⚠️ Chế độ dự phòng');
        
        // EMERGENCY FALLBACK: Generate simple straight lines when backend fails
        const R = 0.04;
        for (let i = 0; i < 8; i++) {
            const startLat = centerLat + (Math.random() - 0.5) * R;
            const startLng = centerLng + (Math.random() - 0.5) * R;
            const endLat = startLat + (Math.random() - 0.5) * 0.015;
            const endLng = startLng + (Math.random() - 0.5) * 0.015;
            
            const fallbackPath = [[startLat, startLng], [endLat, endLng]];
            const severity = Math.random() > 0.5 ? 'severe' : 'moderate';
            const streetName = `Đường Dự Phòng ${i + 1}`;
            const distance = calculateDistance(startLat, startLng, endLat, endLng) * 1000;
            
            const color = severity === 'severe' ? '#DC2626' : '#F59E0B';
            const weight = severity === 'severe' ? 7 : 5;
            const statusText = severity === 'severe' 
                ? 'Tắc nghẽn nghiêm trọng' 
                : 'Ùn ứ vừa phải';
            
            L.polyline(fallbackPath, {
                color: color,
                weight: weight,
                opacity: 0.6,
                lineCap: 'round',
                lineJoin: 'round',
                dashArray: '10, 10'
            }).addTo(map).bindPopup(
                `<b>⚠️ ${statusText}</b><br>` +
                `<strong>Đường:</strong> ${streetName}<br>` +
                `<strong>Độ dài:</strong> ~${(distance / 1000).toFixed(2)} km<br>` +
                `<small>(Chế độ dự phòng - Server offline)</small>`
            );
            
            segments.push({
                path: fallbackPath,
                severity: severity,
                streetName: streetName,
                distance: distance,
                duration: Math.round(distance / 8.33),
                centerDistance: calculateDistance(centerLat, centerLng, startLat, startLng),
                isFallback: true
            });
        }
        
        console.log(`✅ Generated ${segments.length} emergency fallback routes`);
    }

    // CRITICAL: Update PERSISTENT global data for CHATBOT CONTEXT
    window.SIMULATED_TRAFFIC_DATA[locationKey].lat = centerLat;
    window.SIMULATED_TRAFFIC_DATA[locationKey].lng = centerLng;
    window.SIMULATED_TRAFFIC_DATA[locationKey].segments = segments;
    window.SIMULATED_TRAFFIC_DATA[locationKey].loaded = true;
    window.SIMULATED_TRAFFIC_DATA.lastUpdated = new Date().toISOString();

    console.log(`✅ Stored ${segments.length} traffic segments in global context`);
    console.log('📊 Street names for chatbot:', segments.map(s => s.streetName));
    
    // Update UI status
    updateTrafficStatus(`✅ Đã tải các tuyến đường`);
}

/**
 * Update traffic density status text
 * @param {string} message - Status message
 */
function updateTrafficStatus(message) {
    const statusElement = document.querySelector('#content-density h4 span');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.className = 'text-green-600';
    }
}

/**
 * Redraw existing segments on map with location markers (for tab switching)
 * @param {Object} map - Leaflet map instance
 * @param {string} locationKey - Location key
 */
function redrawExistingSegments(map, locationKey) {
    const data = window.SIMULATED_TRAFFIC_DATA[locationKey];
    
    // Draw 5km radius circle for this location (matching fetchRealTrafficRoads)
    const circleLabel = locationKey === 'userLocation' 
        ? 'Vị trí của bạn' 
        : 'Đắk Lắk';
    
    L.circle([data.lat, data.lng], {
        color: '#3B82F6',
        fillColor: '#3B82F6',
        fillOpacity: 0.1,
        radius: 5000, // 5km radius
        weight: 2,
        dashArray: '5, 10'
    }).addTo(map).bindPopup(`<div class="text-center font-semibold text-blue-600">🔵 Vùng mô phỏng giao thông<br/><small>Bán kính 5km (${circleLabel})</small></div>`);
    
    // Add special marker for Dak Lak location
    if (locationKey === 'dakLakLocation') {
        const dakLakIcon = L.divIcon({
            className: 'custom-div-icon',
            html: "<div style='background-color:#DC2626;width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 0 5px rgba(0,0,0,0.5);'></div>",
            iconSize: [12, 12],
            iconAnchor: [6, 6]
        });
        
        L.marker([data.lat, data.lng], { icon: dakLakIcon })
            .addTo(map)
            .bindPopup('<div class="text-center font-bold text-red-600">📍 Số 42 Phạm Hùng, Đắk Lắk<br/><small>(Điểm giám sát cố định)</small></div>');
    }
    
    // Redraw traffic segments
    data.segments.forEach(segment => {
        const color = segment.severity === 'severe' ? '#DC2626' : '#F59E0B';
        const weight = segment.severity === 'severe' ? 7 : 5;
        const statusText = segment.severity === 'severe' 
            ? 'Tắc nghẽn nghiêm trọng' 
            : 'Ùn ứ vừa phải';
        
        L.polyline(segment.path, {
            color: color,
            weight: weight,
            opacity: 1.0,
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(map).bindPopup(
            `<b>⚠️ ${statusText}</b><br>` +
            `<strong>Đường:</strong> ${segment.streetName}<br>` +
            `<strong>Độ dài:</strong> ${(segment.distance / 1000).toFixed(2)} km`
        );
    });
    
    updateTrafficStatus(`✅ Hiển thị ${data.segments.length} tuyến đường`);
}

/**
 * Calculate distance between two points (Haversine formula)
 * @param {number} lat1 - Latitude 1
 * @param {number} lng1 - Longitude 1
 * @param {number} lat2 - Latitude 2
 * @param {number} lng2 - Longitude 2
 * @returns {number} Distance in kilometers
 */
function calculateDistance(lat1, lng1, lat2, lng2) {
    const R = 6371; // Earth radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

/**
 * Generate dual-location traffic data
 * Fetches traffic for both user location and Dak Lak location
 * NOTE: Radius circles are now drawn inside fetchRealTrafficRoads()
 * @param {Object} map - Leaflet map instance
 * @param {number} userLat - User latitude
 * @param {number} userLng - User longitude
 */
async function generateDualLocationTrafficData(map, userLat, userLng) {
    // Generate traffic data for user location (includes 5km circle)
    await fetchRealTrafficRoads(map, userLat, userLng, 'userLocation');
    
    // Generate traffic data for Dak Lak location (No. 42 Pham Hung, Tan An Ward)
    const dakLakLat = 12.6976;
    const dakLakLng = 108.0674;
    
    await fetchRealTrafficRoads(map, dakLakLat, dakLakLng, 'dakLakLocation');
    
    // Add marker for Dak Lak reference point
    const dakLakIcon = L.divIcon({
        className: 'custom-div-icon',
        html: "<div style='background-color:#DC2626;width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 0 5px rgba(0,0,0,0.5);'></div>",
        iconSize: [12, 12],
        iconAnchor: [6, 6]
    });
    
    L.marker([dakLakLat, dakLakLng], { icon: dakLakIcon })
        .addTo(map)
        .bindPopup('<div class="text-center font-bold text-red-600">📍 Số 42 Phạm Hùng, Đắk Lắk<br/><small>(Điểm giám sát cố định)</small></div>');
}

/**
 * Analyze traffic severity near a specific location WITH STREET NAMES (Visual Count + Unique Names)
 * @param {string} locationKey - 'userLocation' or 'dakLakLocation'
 * @returns {Object} Analysis result with segment counts matching map visuals and grouped street names
 */
function analyzeTrafficAtLocation(locationKey) {
    console.log(`🔍 Analyzing traffic for: ${locationKey}`);
    
    const locationData = window.SIMULATED_TRAFFIC_DATA[locationKey];
    
    console.log(`📦 Location data exists:`, !!locationData);
    console.log(`📦 Segments array:`, locationData ? locationData.segments : 'N/A');
    console.log(`📦 Data loaded:`, locationData ? locationData.loaded : 'N/A');
    
    if (!locationData || !locationData.segments || locationData.segments.length === 0 || !locationData.loaded) {
        console.warn(`⚠️ No traffic data available for ${locationKey}`);
        return {
            status: 'unknown',
            message: 'Không có dữ liệu giao thông cho vị trí này. Vui lòng mở tab "Mật Độ Giao Thông" để tải dữ liệu.',
            severeSegmentCount: 0,
            moderateSegmentCount: 0,
            totalSegments: 0,
            severeStreets: [],
            moderateStreets: []
        };
    }
    
    console.log(`✅ Processing ${locationData.segments.length} segments for ${locationKey}`);

    // Step 1: Filter segments by severity (these match the visual lines on map)
    const severeSegments = locationData.segments.filter(s => s.severity === 'severe');
    const moderateSegments = locationData.segments.filter(s => s.severity === 'moderate');
    
    // Step 2: Count total segments (VISUAL CONSISTENCY - matches map line counts)
    const severeSegmentCount = severeSegments.length;
    const moderateSegmentCount = moderateSegments.length;
    
    // Step 3: Group segments by street name and count occurrences
    const severeStreetMap = new Map();
    const moderateStreetMap = new Map();
    
    severeSegments.forEach(segment => {
        if (segment.streetName) {
            const count = severeStreetMap.get(segment.streetName) || 0;
            severeStreetMap.set(segment.streetName, count + 1);
        }
    });
    
    moderateSegments.forEach(segment => {
        if (segment.streetName && !severeStreetMap.has(segment.streetName)) {
            const count = moderateStreetMap.get(segment.streetName) || 0;
            moderateStreetMap.set(segment.streetName, count + 1);
        }
    });
    
    // Convert Maps to formatted arrays with segment counts
    const severeStreets = Array.from(severeStreetMap.entries()).map(([name, count]) => ({
        name: name,
        count: count
    }));
    
    const moderateStreets = Array.from(moderateStreetMap.entries()).map(([name, count]) => ({
        name: name,
        count: count
    }));

    let status = 'clear';
    let message = '';

    if (severeSegmentCount >= 3) {
        status = 'severe';
        message = `⚠️ CẢNH BÁO NGHIÊM TRỌNG: Phát hiện tắc nghẽn tại:\n\n`;
        message += `Tắc nghẽn nặng:\n`;
        severeStreets.forEach(street => {
            if (street.count > 1) {
                message += `🔴 ${street.name} (${street.count} đoạn)\n`;
            } else {
                message += `🔴 ${street.name}\n`;
            }
        });
        if (moderateStreets.length > 0) {
            message += `\nÙn ứ nhẹ:\n`;
            moderateStreets.slice(0, 3).forEach(street => {
                if (street.count > 1) {
                    message += `🟠 ${street.name} (${street.count} đoạn)\n`;
                } else {
                    message += `🟠 ${street.name}\n`;
                }
            });
        }
        message += `\n💡 Khuyến nghị: Nên tìm tuyến đường thay thế!`;
    } else if (severeSegmentCount > 0) {
        status = 'warning';
        message = `⚠️ Cảnh báo giao thông:\n\n`;
        message += `Tắc nghẽn:\n`;
        severeStreets.forEach(street => {
            if (street.count > 1) {
                message += `🔴 ${street.name} (${street.count} đoạn)\n`;
            } else {
                message += `🔴 ${street.name}\n`;
            }
        });
        if (moderateStreets.length > 0) {
            message += `\nÙn ứ:\n`;
            moderateStreets.slice(0, 3).forEach(street => {
                if (street.count > 1) {
                    message += `🟠 ${street.name} (${street.count} đoạn)\n`;
                } else {
                    message += `🟠 ${street.name}\n`;
                }
            });
        }
        message += `\nDi chuyển cẩn thận qua khu vực này.`;
    } else if (moderateSegmentCount >= 3) {
        status = 'moderate';
        message = `Lưu lượng xe khá đông tại:\n\n`;
        moderateStreets.forEach(street => {
            if (street.count > 1) {
                message += `🟠 ${street.name} (${street.count} đoạn)\n`;
            } else {
                message += `🟠 ${street.name}\n`;
            }
        });
        message += `\nVẫn di chuyển được nhưng nên chuẩn bị thời gian dự phòng.`;
    } else {
        status = 'clear';
        message = `✅ Giao thông thông thoáng\n\nKhông phát hiện ùn tắc nghiêm trọng trong khu vực. An toàn khi di chuyển.`;
    }

    return {
        status: status,
        message: message,
        severeSegmentCount: severeSegmentCount,
        moderateSegmentCount: moderateSegmentCount,
        totalSegments: locationData.segments.length,
        severeStreets: severeStreets,
        moderateStreets: moderateStreets,
        location: {
            lat: locationData.lat,
            lng: locationData.lng
        }
    };
}

// Export functions for use in main.js
window.TrafficDataModule = {
    fetchRealTrafficRoads,
    generateDualLocationTrafficData,
    analyzeTrafficAtLocation,
    calculateDistance,
    updateTrafficStatus
};
