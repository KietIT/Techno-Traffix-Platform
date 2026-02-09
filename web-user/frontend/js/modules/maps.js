/**
 * Maps Module - Initialize Leaflet maps for traffic and air quality
 * Uses Browser Geolocation API to center on user's position
 * Always shows fixed predefined zone data + live GPS tracking with its own routes
 */

let API_BASE = '';
let trafficMap = null;
let airMap = null;

// GPS tracking state
let currentLocation = null;
let currentRoutes = null;
let userMarker = null;
let userAccuracyCircle = null;
let watchId = null;
let gpsRoutesLoaded = false;
let gpsRouteCenter = null;

// GPS zone overlays (cleared/redrawn when user moves significantly)
let gpsZoneCircle = null;
let gpsRoutePolylines = [];

// Fixed zone overlays (loaded once on init, never cleared)
let fixedZoneLayers = [];

/**
 * Returns the user's current location and cached traffic routes.
 */
export function getCurrentLocation() {
    if (!currentLocation) return null;
    return {
        lat: currentLocation.lat,
        lng: currentLocation.lng,
        routes: currentRoutes || [],
    };
}

export function initMaps(apiBase) {
    API_BASE = apiBase;

    const trafficMapContainer = document.getElementById('map-traffic');
    const airMapContainer = document.getElementById('map-air');

    if (trafficMapContainer) {
        initTrafficMap(trafficMapContainer);
    }

    if (airMapContainer) {
        initAirMap(airMapContainer);
    }

    // Invalidate map size when tabs become visible (fixes mobile rendering)
    window.addEventListener('resize', () => {
        if (trafficMap) setTimeout(() => trafficMap.invalidateSize(), 100);
        if (airMap) setTimeout(() => airMap.invalidateSize(), 100);
    });

    // Also listen for tab switch via MutationObserver on the tab panels
    const trafficPanel = document.getElementById('tab-traffic');
    const airPanel = document.getElementById('tab-air');

    if (trafficPanel) {
        observePanelVisibility(trafficPanel, () => {
            if (trafficMap) {
                setTimeout(() => trafficMap.invalidateSize(), 200);
            }
        });
    }

    if (airPanel) {
        observePanelVisibility(airPanel, () => {
            if (airMap) {
                setTimeout(() => airMap.invalidateSize(), 200);
            }
        });
    }

    console.log('Maps module initialized');
}

/**
 * Observe when a tab panel becomes active (class change).
 */
function observePanelVisibility(panel, callback) {
    const observer = new MutationObserver(() => {
        if (panel.classList.contains('tab-panel--active')) {
            callback();
        }
    });
    observer.observe(panel, { attributes: true, attributeFilter: ['class'] });
}

function initTrafficMap(container) {
    const defaultCenter = [12.6976, 108.0674];

    trafficMap = L.map(container, {
        zoomControl: true,
        attributionControl: true
    }).setView(defaultCenter, 14);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        maxZoom: 19
    }).addTo(trafficMap);

    // Load fixed predefined zones (always visible)
    loadFixedZones();

    // Start GPS tracking
    startGPSTracking();
}

function initAirMap(container) {
    const center = [12.6976, 108.0674];

    airMap = L.map(container, {
        zoomControl: true,
        attributionControl: true
    }).setView(center, 12);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        maxZoom: 19
    }).addTo(airMap);

    // Load real AQI data for the default center
    loadAQIData(center[0], center[1]);

    // Add AQI legend
    addAQILegend();
}

// ==================== GPS TRACKING ====================

function startGPSTracking() {
    if (!navigator.geolocation) {
        console.warn('Geolocation not supported, using default location');
        useFallbackLocation();
        return;
    }

    watchId = navigator.geolocation.watchPosition(
        onGPSSuccess,
        onGPSError,
        {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 5000
        }
    );
}

function onGPSSuccess(position) {
    const { latitude, longitude, accuracy } = position.coords;

    currentLocation = { lat: latitude, lng: longitude };

    // Update user marker on every position change
    updateUserMarker(latitude, longitude, accuracy);

    // Load GPS routes once on first fix, or when moved > 2km
    if (!gpsRoutesLoaded) {
        gpsRoutesLoaded = true;
        trafficMap.setView([latitude, longitude], 14);
        loadGPSRoutes(latitude, longitude);
    } else {
        const dist = haversineDistance(
            gpsRouteCenter?.lat || latitude,
            gpsRouteCenter?.lng || longitude,
            latitude, longitude
        );
        if (dist > 2000) {
            loadGPSRoutes(latitude, longitude);
        }
    }
}

function onGPSError(error) {
    console.warn(`Geolocation error: ${error.message}`);
    if (!currentLocation) {
        useFallbackLocation();
    }
}

function useFallbackLocation() {
    const lat = 12.6976;
    const lng = 108.0674;
    currentLocation = { lat, lng };
    updateUserMarker(lat, lng, 500);
    trafficMap.setView([lat, lng], 14);
    gpsRoutesLoaded = true;
    loadGPSRoutes(lat, lng);
}

function updateUserMarker(lat, lng, accuracy) {
    if (!trafficMap) return;

    if (userMarker) {
        userMarker.setLatLng([lat, lng]);
    } else {
        userMarker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'user-location-icon',
                html: `<div style="
                    position:relative;
                    width:18px;height:18px;
                ">
                    <div style="
                        position:absolute;top:0;left:0;
                        width:18px;height:18px;
                        background:#3b82f6;border-radius:50%;
                        border:3px solid #fff;
                        box-shadow:0 0 8px rgba(59,130,246,0.6);
                    "></div>
                    <div style="
                        position:absolute;top:-6px;left:-6px;
                        width:30px;height:30px;
                        background:rgba(59,130,246,0.15);
                        border-radius:50%;
                        animation:pulse 2s ease-out infinite;
                    "></div>
                </div>`,
                iconSize: [18, 18],
                iconAnchor: [9, 9]
            }),
            zIndexOffset: 1000
        })
            .bindPopup('<strong>Vị trí của bạn</strong>')
            .addTo(trafficMap);

        // Add pulse animation style
        if (!document.getElementById('gps-pulse-style')) {
            const style = document.createElement('style');
            style.id = 'gps-pulse-style';
            style.textContent = `
                @keyframes pulse {
                    0% { transform: scale(1); opacity: 1; }
                    100% { transform: scale(2.5); opacity: 0; }
                }
                .user-location-icon { background: none !important; border: none !important; }
                .fixed-zone-label { background: none !important; border: none !important; }
            `;
            document.head.appendChild(style);
        }
    }

    // Update accuracy circle
    if (accuracy && accuracy < 5000) {
        if (userAccuracyCircle) {
            userAccuracyCircle.setLatLng([lat, lng]);
            userAccuracyCircle.setRadius(accuracy);
        } else {
            userAccuracyCircle = L.circle([lat, lng], {
                radius: accuracy,
                color: '#3b82f6',
                weight: 1,
                opacity: 0.3,
                fillColor: '#3b82f6',
                fillOpacity: 0.06
            }).addTo(trafficMap);
        }
    }
}

// ==================== FIXED PREDEFINED ZONES ====================

/**
 * Load all predefined traffic zones from the backend and draw them permanently.
 * These never get cleared — they are always visible on the map.
 */
async function loadFixedZones() {
    try {
        const zonesRes = await fetch(`${API_BASE}/traffic/zones`);
        if (!zonesRes.ok) return;
        const { zones } = await zonesRes.json();

        for (const zone of zones) {
            const dataRes = await fetch(`${API_BASE}/traffic/data?zone_id=${zone.id}`);
            if (!dataRes.ok) continue;
            const data = await dataRes.json();

            const radiusM = (zone.radius_km || 3) * 1000;

            // Zone circle
            const circle = L.circle([zone.center.lat, zone.center.lng], {
                radius: radiusM,
                color: '#8b5cf6',
                weight: 2,
                opacity: 0.4,
                fillColor: '#8b5cf6',
                fillOpacity: 0.04,
                dashArray: '8 6'
            })
                .bindPopup(`<strong>${zone.name}</strong><br>Bán kính: ${zone.radius_km} km`)
                .addTo(trafficMap);
            fixedZoneLayers.push(circle);

            // Zone center label
            const label = L.marker([zone.center.lat, zone.center.lng], {
                icon: L.divIcon({
                    className: 'fixed-zone-label',
                    html: `<div style="
                        background:rgba(139,92,246,0.9);color:#fff;
                        padding:4px 10px;border-radius:12px;
                        font-size:12px;font-weight:600;
                        white-space:nowrap;text-align:center;
                        box-shadow:0 2px 6px rgba(0,0,0,0.2);
                    ">${zone.name}</div>`,
                    iconSize: [0, 0],
                    iconAnchor: [0, -10]
                }),
                interactive: false
            }).addTo(trafficMap);
            fixedZoneLayers.push(label);

            // Traffic route polylines
            (data.routes || []).forEach(route => {
                const color = route.severity === 'severe' ? '#ef4444' : '#f59e0b';
                const weight = route.severity === 'severe' ? 6 : 4;

                const polyline = L.polyline(route.coordinates, {
                    color: color,
                    weight: weight,
                    opacity: 0.75,
                    lineJoin: 'round',
                    lineCap: 'round'
                })
                    .bindPopup(`<strong>${route.name}</strong><br>
                        Mức độ: ${route.severity === 'severe' ? 'Tắc nghiêm trọng' : 'Đông xe'}`)
                    .addTo(trafficMap);
                fixedZoneLayers.push(polyline);
            });

            console.log(`Fixed zone "${zone.name}": ${(data.routes || []).length} routes loaded`);
        }
    } catch (err) {
        console.warn('Failed to load fixed zones:', err.message);
    }
}

// ==================== GPS TRAFFIC ROUTES ====================

/**
 * Fetch traffic routes around the user's GPS position.
 * Only manages GPS-specific overlays — fixed zones are never touched.
 */
async function loadGPSRoutes(centerLat, centerLng) {
    clearGPSOverlays();

    let routes = [];

    try {
        const url = `${API_BASE}/traffic/data?lat=${centerLat}&lng=${centerLng}&radius_km=3`;
        const response = await fetch(url);

        if (response.ok) {
            const data = await response.json();
            routes = (data.routes || []).map(r => ({
                name: r.name,
                severity: r.severity,
                points: r.coordinates
            }));
        }
    } catch (err) {
        console.warn('Traffic API unavailable for GPS zone:', err.message);
    }

    currentRoutes = routes;
    gpsRouteCenter = { lat: centerLat, lng: centerLng };

    // Draw GPS zone circle (blue)
    gpsZoneCircle = L.circle([centerLat, centerLng], {
        radius: 3000,
        color: '#3b82f6',
        weight: 2,
        opacity: 0.4,
        fillColor: '#3b82f6',
        fillOpacity: 0.04,
        dashArray: '8 6'
    })
        .bindPopup('<strong>Khu vực của bạn</strong><br>Bán kính: 3 km')
        .addTo(trafficMap);

    // Draw GPS route polylines
    routes.forEach(route => {
        const color = route.severity === 'severe' ? '#ef4444' : '#f59e0b';
        const weight = route.severity === 'severe' ? 6 : 4;

        const polyline = L.polyline(route.points, {
            color: color,
            weight: weight,
            opacity: 0.75,
            lineJoin: 'round',
            lineCap: 'round'
        })
            .bindPopup(`<strong>${route.name}</strong><br>
                Mức độ: ${route.severity === 'severe' ? 'Tắc nghiêm trọng' : 'Đông xe'}`)
            .addTo(trafficMap);

        gpsRoutePolylines.push(polyline);
    });

    console.log(`GPS zone: ${routes.length} routes around [${centerLat.toFixed(4)}, ${centerLng.toFixed(4)}]`);
}

/**
 * Clear only GPS zone overlays (circle + routes). Fixed zones are never touched.
 */
function clearGPSOverlays() {
    gpsRoutePolylines.forEach(layer => trafficMap.removeLayer(layer));
    gpsRoutePolylines = [];

    if (gpsZoneCircle) {
        trafficMap.removeLayer(gpsZoneCircle);
        gpsZoneCircle = null;
    }
}

// ==================== UTILITIES ====================

function haversineDistance(lat1, lng1, lat2, lng2) {
    const R = 6371000;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}


// ==================== AIR QUALITY ====================

/**
 * Fetch real AQI data from the backend (Open-Meteo API) and render markers.
 */
async function loadAQIData(lat, lng) {
    if (!airMap) return;

    try {
        const url = `${API_BASE}/air-quality?lat=${lat}&lng=${lng}&radius_km=8`;
        const response = await fetch(url);

        if (!response.ok) {
            console.warn('AQI API error, using fallback');
            return;
        }

        const data = await response.json();

        // Render center point (detailed)
        if (data.center) {
            addAQIDetailMarker(data.center);
        }

        // Render grid points
        (data.stations || []).forEach(point => {
            // Skip if same coords as center (avoid overlap)
            if (data.center &&
                Math.abs(point.lat - data.center.lat) < 0.01 &&
                Math.abs(point.lng - data.center.lng) < 0.01) {
                return;
            }
            addAQIGridMarker(point);
        });

        console.log(`AQI: loaded ${(data.stations || []).length} data points around [${lat}, ${lng}]`);

    } catch (err) {
        console.warn('Failed to load AQI data:', err.message);
    }
}

/**
 * Render a detailed AQI marker at the center point with pollutant breakdown.
 */
function addAQIDetailMarker(point) {
    // Build pollutant rows
    let pollutantRows = '';
    if (point.pollutants) {
        const entries = Object.entries(point.pollutants).filter(([, v]) => v != null);
        pollutantRows = entries.map(([name, val]) =>
            `<tr><td style="padding:2px 8px 2px 0;color:#64748b;">${name}</td>
             <td style="padding:2px 0;font-weight:600;">${val} µg/m³</td></tr>`
        ).join('');
    }

    const uvInfo = point.uv_index != null
        ? `<div style="margin-top:6px;font-size:0.8em;color:#64748b;">☀️ UV: ${point.uv_index}</div>` : '';

    const timeInfo = point.time
        ? `<div style="font-size:0.75em;color:#94a3b8;margin-top:4px;">🕐 ${point.time}</div>` : '';

    const popup = `
        <div style="min-width:200px;font-family:system-ui,sans-serif;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                <div style="
                    width:48px;height:48px;border-radius:50%;
                    background:${point.color};color:#fff;
                    display:flex;align-items:center;justify-content:center;
                    font-size:1.1em;font-weight:700;
                ">${point.aqi}</div>
                <div>
                    <div style="font-weight:700;font-size:1em;">AQI: ${point.aqi}</div>
                    <div style="color:${point.color};font-weight:600;font-size:0.85em;">${point.status}</div>
                </div>
            </div>
            <div style="background:#f8fafc;border-radius:8px;padding:8px;margin-bottom:8px;">
                <div style="font-size:0.85em;color:#334155;line-height:1.5;">${point.advice}</div>
            </div>
            ${pollutantRows ? `
                <div style="font-weight:600;font-size:0.85em;margin-bottom:4px;">Chất ô nhiễm:</div>
                <table style="font-size:0.82em;width:100%;">${pollutantRows}</table>
            ` : ''}
            ${uvInfo}
            ${timeInfo}
        </div>
    `;

    L.circleMarker([point.lat, point.lng], {
        radius: 22,
        fillColor: point.color,
        color: '#fff',
        weight: 3,
        opacity: 1,
        fillOpacity: 0.85
    }).bindPopup(popup, { maxWidth: 280 }).addTo(airMap);

    // AQI number label on top of the circle
    L.marker([point.lat, point.lng], {
        icon: L.divIcon({
            className: 'aqi-label',
            html: `<div style="
                color:#fff;font-weight:700;font-size:13px;
                text-align:center;line-height:1;
                text-shadow:0 1px 2px rgba(0,0,0,0.3);
            ">${point.aqi}</div>`,
            iconSize: [40, 20],
            iconAnchor: [20, 10]
        }),
        interactive: false
    }).addTo(airMap);
}

/**
 * Render a simpler AQI marker for grid points.
 */
function addAQIGridMarker(point) {
    const popup = `
        <div style="font-family:system-ui,sans-serif;">
            <div style="font-weight:700;">AQI: ${point.aqi}</div>
            <div style="color:${point.color};font-weight:600;font-size:0.9em;">${point.status}</div>
            <div style="font-size:0.85em;color:#64748b;margin-top:4px;">${point.advice}</div>
        </div>
    `;

    L.circleMarker([point.lat, point.lng], {
        radius: 16,
        fillColor: point.color,
        color: '#fff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.75
    }).bindPopup(popup, { maxWidth: 250 }).addTo(airMap);

    L.marker([point.lat, point.lng], {
        icon: L.divIcon({
            className: 'aqi-label',
            html: `<div style="
                color:#fff;font-weight:700;font-size:11px;
                text-align:center;line-height:1;
                text-shadow:0 1px 2px rgba(0,0,0,0.3);
            ">${point.aqi}</div>`,
            iconSize: [30, 16],
            iconAnchor: [15, 8]
        }),
        interactive: false
    }).addTo(airMap);
}

/**
 * Add AQI color legend to the air quality map.
 */
function addAQILegend() {
    const legend = L.control({ position: 'bottomright' });

    legend.onAdd = function () {
        const div = L.DomUtil.create('div', 'aqi-legend');
        div.style.cssText = `
            background: white; padding: 10px 14px; border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px;
            font-family: system-ui, sans-serif; line-height: 1.8;
        `;

        div.innerHTML = `
            <div style="font-weight:700;margin-bottom:4px;">Chỉ số AQI (US)</div>
            <div><span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#10b981;vertical-align:middle;margin-right:6px;"></span>0-50 Tốt</div>
            <div><span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#f59e0b;vertical-align:middle;margin-right:6px;"></span>51-100 Trung bình</div>
            <div><span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#f97316;vertical-align:middle;margin-right:6px;"></span>101-150 Nhạy cảm</div>
            <div><span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#ef4444;vertical-align:middle;margin-right:6px;"></span>151-200 Không tốt</div>
            <div><span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#7c3aed;vertical-align:middle;margin-right:6px;"></span>201-300 Rất xấu</div>
            <div><span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#991b1b;vertical-align:middle;margin-right:6px;"></span>301+ Nguy hiểm</div>
            <div style="margin-top:6px;font-size:11px;color:#94a3b8;">Nguồn: Open-Meteo</div>
        `;
        return div;
    };

    legend.addTo(airMap);

    // Add CSS for aqi-label icons
    if (!document.getElementById('aqi-label-style')) {
        const style = document.createElement('style');
        style.id = 'aqi-label-style';
        style.textContent = `.aqi-label { background: none !important; border: none !important; }`;
        document.head.appendChild(style);
    }
}
