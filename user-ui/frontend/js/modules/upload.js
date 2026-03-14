/**
 * Upload Module - Handle file upload and AI analysis
 */

let API_BASE = '';
let selectedFile = null;
let _pollTimer = null;
let _abortController = null;

/** Recalculate .tab-panels-container minHeight after content changes. */
function recalcContainerHeight() {
    // Double-rAF ensures the browser has finished layout/paint before measuring.
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            const container = document.querySelector('.tab-panels-container');
            const activePanel = document.querySelector('.tab-panel--active');
            if (container && activePanel) {
                container.style.minHeight = `${Math.max(activePanel.scrollHeight, 400)}px`;
            }
        });
    });
}

function showUploadError(message) {
    const el = document.getElementById('upload-error');
    if (!el) { console.error(message); return; }
    el.textContent = message;
    el.classList.remove('hidden');
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function clearUploadError() {
    const el = document.getElementById('upload-error');
    if (el) el.classList.add('hidden');
}

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

// Resets upload form state only — no scrolling.
// Called automatically after a successful analysis so the zone is ready for a new file.
function resetUploadState() {
    selectedFile = null;

    const fileInput = document.getElementById('media-input');
    if (fileInput) fileInput.value = '';

    const uploadZone = document.getElementById('upload-zone');
    if (uploadZone) {
        uploadZone.querySelector('.upload-zone__text').textContent = 'Kéo thả hoặc nhấn để chọn file';
        uploadZone.querySelector('.upload-zone__hint').textContent = 'Hỗ trợ ảnh (JPG, PNG) và video (MP4, WebM)';
    }

    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) analyzeBtn.disabled = true;

}

function handleFileSelect(file) {
    clearUploadError();
    selectedFile = file;
    const isVideo = file.type.startsWith('video/');
    const isImage = file.type.startsWith('image/');

    if (!isVideo && !isImage) {
        showUploadError('Vui lòng chọn file ảnh hoặc video!');
        return;
    }

    const MAX_IMAGE_MB = 20;
    const MAX_VIDEO_MB = 200;
    const maxBytes = isVideo ? MAX_VIDEO_MB * 1024 * 1024 : MAX_IMAGE_MB * 1024 * 1024;
    if (file.size > maxBytes) {
        showUploadError(`File quá lớn. Kích thước tối đa: ${isVideo ? MAX_VIDEO_MB : MAX_IMAGE_MB}MB (file hiện tại: ${(file.size / 1024 / 1024).toFixed(1)}MB)`);
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

function stopPolling() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
    if (_abortController) { _abortController.abort(); _abortController = null; }
}

function setProgress(pct, label) {
    const progressContainer = document.getElementById('upload-progress');
    if (!progressContainer) return;
    progressContainer.classList.remove('hidden');
    progressContainer.querySelector('.upload-progress__bar').style.width = pct + '%';
    progressContainer.querySelector('.upload-progress__label').textContent = label;
}

export async function handleAnalysis() {
    clearUploadError();
    if (!selectedFile) {
        showUploadError('Vui lòng chọn file trước!');
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

    const cancelBtn = document.getElementById('cancel-analysis-btn');
    if (cancelBtn) {
        cancelBtn.classList.remove('hidden');
        cancelBtn.onclick = () => {
            stopPolling();
            finishAnalysis(false);
        };
    }

    _abortController = new AbortController();
    let analysisSucceeded = false;

    const TIMEOUT_MS = isVideo ? 10 * 60 * 1000 : 2 * 60 * 1000;

    try {
        // ---- Phase 1: Upload file & get task_id ----
        setProgress(0, 'Đang tải lên...');

        const uploadRes = await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            _abortController.signal.addEventListener('abort', () => {
                xhr.abort();
                reject(new Error('Đã hủy'));
            });

            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    // Upload maps to 0-30% of overall progress
                    const uploadPct = Math.round((e.loaded / e.total) * 30);
                    setProgress(uploadPct, uploadPct < 30 ? `Đang tải lên... ${Math.round(e.loaded / e.total * 100)}%` : 'Đã tải lên, đang gửi xử lý...');
                }
            };

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try { resolve(JSON.parse(xhr.responseText)); }
                    catch { reject(new Error('Invalid server response')); }
                } else {
                    reject(new Error(`Server error (${xhr.status})`));
                }
            };
            xhr.onerror = () => reject(new Error('Network error'));
            xhr.open('POST', `${API_BASE}${endpoint}`);
            xhr.send(formData);
        });

        if (!uploadRes.success || !uploadRes.task_id) {
            throw new Error(uploadRes.error || 'Upload failed');
        }

        const taskId = uploadRes.task_id;
        console.log(`Task submitted: ${taskId}`);
        setProgress(30, 'Đang phân tích AI...');

        // ---- Phase 2: Poll for status ----
        const pollInterval = isVideo ? 2000 : 1000;
        const startTime = Date.now();

        const data = await new Promise((resolve, reject) => {
            let polling = false;  // guard against overlapping async callbacks
            _pollTimer = setInterval(async () => {
                if (polling) return;  // previous fetch still in-flight

                if (_abortController && _abortController.signal.aborted) {
                    stopPolling();
                    reject(new Error('Đã hủy'));
                    return;
                }

                if (Date.now() - startTime > TIMEOUT_MS) {
                    stopPolling();
                    reject(new Error('Quá thời gian xử lý. Vui lòng thử lại.'));
                    return;
                }

                polling = true;
                try {
                    const res = await fetch(`${API_BASE}/analyze/status/${taskId}`);
                    const status = await res.json();

                    if (status.status === 'processing' || status.status === 'pending') {
                        // Map server progress (0-100) into 30-100% range on the bar
                        const mappedPct = 30 + Math.round((status.progress || 0) * 0.7);
                        setProgress(Math.min(mappedPct, 99), status.progress_message || 'Đang xử lý...');
                    } else if (status.status === 'completed') {
                        stopPolling();
                        resolve(status.result);
                    } else if (status.status === 'failed') {
                        stopPolling();
                        reject(new Error(status.error || 'Processing failed'));
                    }
                } catch (err) {
                    // Network blip — keep polling unless aborted
                    if (_abortController && _abortController.signal.aborted) {
                        stopPolling();
                        reject(new Error('Đã hủy'));
                    }
                    console.warn('Poll error (retrying):', err);
                } finally {
                    polling = false;
                }
            }, pollInterval);
        });

        console.log('Response data:', JSON.stringify(data, null, 2));

        if (data && data.success) {
            setProgress(100, 'Hoàn tất!');
            displayResults(data, isVideo);
            resetUploadState();
            analysisSucceeded = true;
        } else {
            throw new Error((data && data.error) || 'Lỗi không xác định');
        }

    } catch (error) {
        if (error.message !== 'Đã hủy') {
            console.error('Analysis error:', error);
            showUploadError(`Lỗi phân tích: ${error.message || error.toString()}`);
        }
    } finally {
        finishAnalysis(analysisSucceeded);
    }
}

function finishAnalysis(succeeded) {
    stopPolling();
    document.getElementById('loading-state').classList.add('hidden');
    const progressContainer = document.getElementById('upload-progress');
    if (progressContainer) progressContainer.classList.add('hidden');
    const cancelBtn = document.getElementById('cancel-analysis-btn');
    if (cancelBtn) cancelBtn.classList.add('hidden');
    if (!succeeded) {
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
        <video id="result-video" controls preload="metadata" style="display: none;"></video>
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
            // Video element now has its natural dimensions — recalculate height
            recalcContainerHeight();
        };

        newResultVideo.oncanplay = () => {
            console.log('Video can start playing');
        };

    } else {
        newResultVideo.style.display = 'none';
        newResultImage.style.display = 'block';
        newResultImage.src = data.media_url;

        newResultImage.onerror = () => {
            console.error('Image load error');
            newResultImage.alt = 'Không thể tải ảnh';
        };
    }

    // --- Vehicle count card + breakdown + JSON download (video only) ---
    const countCard = document.getElementById('result-count');
    const breakdown = document.getElementById('vehicle-breakdown');
    const jsonSection = document.getElementById('json-download-section');

    if (isVideo && data.vehicle_counts && Object.keys(data.vehicle_counts).length > 0) {
        // Total count card
        countCard.classList.remove('hidden');
        countCard.querySelector('.result-card__value').textContent = data.total_vehicles ?? 0;

        // Per-class breakdown chips
        breakdown.classList.remove('hidden');
        const list = document.getElementById('vehicle-breakdown-list');
        list.innerHTML = Object.entries(data.vehicle_counts)
            .sort((a, b) => b[1] - a[1])
            .map(([cls, cnt]) => `<span class="vehicle-chip">${cls}: ${cnt}</span>`)
            .join('');

        // JSON download button
        if (data.json_url) {
            jsonSection.classList.remove('hidden');
            document.getElementById('json-download-btn').href = data.json_url;
        } else {
            jsonSection.classList.add('hidden');
        }
    } else {
        countCard.classList.add('hidden');
        breakdown.classList.add('hidden');
        jsonSection.classList.add('hidden');
    }

    // Show results section
    resultsSection.classList.remove('hidden');

    // Recalculate container height so content is scrollable
    recalcContainerHeight();

    console.log('Results displayed successfully');
}
