/**
 * Techno Traffix - Main Application Entry Point
 * ES Module Architecture
 */

import { initTabs } from './modules/tabs.js';
import { initUpload, handleAnalysis } from './modules/upload.js';
import { initMaps } from './modules/maps.js';
import { initChat } from './modules/chat.js';
import { initCommunity } from './modules/community.js';
import { initParticles } from './modules/particles.js';

// API Base URL - Use relative path since frontend and backend are on same server
const API_BASE = '/api';

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Initializing Techno Traffix...');

    // Initialize all modules
    initTabs();
    initUpload(API_BASE);
    initMaps(API_BASE);
    initChat();
    initCommunity(API_BASE);
    initParticles();

    console.log('✅ Techno Traffix initialized successfully!');
});

// Export for global access if needed
window.TechnoTraffixAPI = API_BASE;
