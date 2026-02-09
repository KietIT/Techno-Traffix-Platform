/**
 * Upload Module - Handle file upload and AI analysis
 */

let API_BASE = '';
let selectedFile = null;

export function initUpload(apiBase) {
    API_BASE = apiBase;

    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('media-input');
    const analyzeBtn = document.getElementById('analyze-btn');

    if (!uploadZone || !fileInput || !analyzeBtn) {
        console.warn('Upload elements not found');
        return;
    }

    // Click to upload
    uploadZone.addEventListener('click', () => fileInput.click());

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('upload-zone--dragging');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('upload-zone--dragging');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('upload-zone--dragging');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // Analyze button
    analyzeBtn.addEventListener('click', (e) => {
        e.preventDefault();
        handleAnalysis();
    });

    console.log('Upload module initialized');
}

function handleFileSelect(file) {
    selectedFile = file;
    const isVideo = file.type.startsWith('video/');
    const isImage = file.type.startsWith('image/');

    if (!isVideo && !isImage) {
        alert('Vui lòng chọn file ảnh hoặc video!');
        return;
    }

    // Update UI
    const uploadZone = document.getElementById('upload-zone');
    const analyzeBtn = document.getElementById('analyze-btn');

    uploadZone.querySelector('.upload-zone__text').textContent = file.name;
    uploadZone.querySelector('.upload-zone__hint').textContent =
        `${isVideo ? 'Video' : 'Ảnh'} - ${(file.size / (1024 * 1024)).toFixed(2)} MB`;

    analyzeBtn.disabled = false;

    console.log(`File selected: ${file.name} (${file.type})`);
}

export async function handleAnalysis() {
    if (!selectedFile) {
        alert('Vui lòng chọn file trước!');
        return;
    }

    const isVideo = selectedFile.type.startsWith('video/');
    const endpoint = isVideo ? '/analyze/video' : '/analyze/image';
    const formData = new FormData();
    formData.append(isVideo ? 'video' : 'image', selectedFile);

    // Show loading
    document.getElementById('loading-state').classList.remove('hidden');
    document.getElementById('results-section').classList.add('hidden');
    document.getElementById('analyze-btn').disabled = true;

    try {
        console.log(`Sending ${isVideo ? 'video' : 'image'} to ${API_BASE}${endpoint}`);

        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            body: formData
        });

        console.log('Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Server error response:', errorText);
            throw new Error(`Server error (${response.status}): ${errorText}`);
        }
        
        const data = await response.json();
        console.log('Response data:', JSON.stringify(data, null, 2));

        if (data.success) {
            displayResults(data, isVideo);
        } else {
            throw new Error(data.error || 'Lỗi không xác định');
        }

    } catch (error) {
        console.error('Analysis error:', error);
        console.error('Error stack:', error.stack);
        alert(`Lỗi phân tích: ${error.message || error.toString()}`);
    } finally {
        document.getElementById('loading-state').classList.add('hidden');
        document.getElementById('analyze-btn').disabled = false;
    }
}

function displayResults(data, isVideo) {
    console.log('Displaying results:', { isVideo, media_url: data.media_url });

    const resultsSection = document.getElementById('results-section');
    const trafficCard = document.getElementById('result-traffic');
    const accidentCard = document.getElementById('result-accident');
    const resultImage = document.getElementById('result-image');
    const resultVideo = document.getElementById('result-video');
    const mediaDisplay = document.getElementById('media-display');

    // Update traffic card - style based on jam status
    const isJam = data.is_traffic_jam;
    trafficCard.className = `result-card ${isJam ? 'result-card--danger' : 'result-card--success'}`;
    trafficCard.querySelector('.result-card__value').textContent = data.traffic_status;

    // Accident card styling
    const hasAccident = data.accident_warning;
    accidentCard.className = `result-card ${hasAccident ? 'result-card--danger' : 'result-card--success'}`;
    accidentCard.querySelector('.result-card__value').textContent = hasAccident ? 'Phát hiện!' : 'Không';

    // Reset media display
    mediaDisplay.innerHTML = `
        <img id="result-image" src="" alt="Kết quả phân tích" style="display: none;">
        <video id="result-video" controls style="display: none;"></video>
    `;

    const newResultImage = document.getElementById('result-image');
    const newResultVideo = document.getElementById('result-video');

    // Display media
    if (isVideo) {
        const videoUrl = data.media_url || data.video_url;
        console.log('Loading video from:', videoUrl);
        
        newResultImage.style.display = 'none';
        newResultVideo.style.display = 'block';
        
        // Set source with cache-busting
        const cacheBuster = `?t=${Date.now()}`;
        newResultVideo.src = videoUrl + cacheBuster;
        
        // Add event handlers
        newResultVideo.onerror = (e) => {
            console.error('Video load error:', e);
            console.error('Video error code:', newResultVideo.error?.code);
            console.error('Video error message:', newResultVideo.error?.message);
            
            // Show user-friendly error with download option
            mediaDisplay.innerHTML = `
                <div style="padding: 2rem; text-align: center; color: var(--text-secondary); background: var(--color-primary-light); border-radius: var(--radius-lg);">
                    <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="margin: 0 auto 1rem; color: var(--color-warning);">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                    </svg>
                    <p style="margin-bottom: 1rem; font-weight: 500;">Video không thể phát trong trình duyệt</p>
                    <p style="margin-bottom: 1.5rem; font-size: 0.875rem; color: var(--text-muted);">Trình duyệt của bạn có thể không hỗ trợ định dạng video này. Vui lòng tải xuống để xem.</p>
                    <a href="${videoUrl}" download class="btn btn--primary" style="display: inline-flex; gap: 0.5rem;">
                        <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                        </svg>
                        Tải Video Xuống
                    </a>
                </div>
            `;
        };

        newResultVideo.onloadeddata = () => {
            console.log('Video loaded successfully');
            console.log('Video dimensions:', newResultVideo.videoWidth, 'x', newResultVideo.videoHeight);
            console.log('Video duration:', newResultVideo.duration);
        };

        newResultVideo.oncanplay = () => {
            console.log('Video can start playing');
        };

        // Try to load
        newResultVideo.load();
        
    } else {
        newResultVideo.style.display = 'none';
        newResultImage.style.display = 'block';
        newResultImage.src = data.media_url;
        
        newResultImage.onerror = () => {
            console.error('Image load error');
            newResultImage.alt = 'Không thể tải ảnh';
        };
    }

    // Show results section with animation
    resultsSection.classList.remove('hidden');
    
    // Scroll to results
    setTimeout(() => {
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);

    console.log('Results displayed successfully');
}
