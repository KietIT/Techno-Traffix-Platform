/**
 * Community Module — Facebook-inspired social feed
 * Posts CRUD, likes/dislikes, comments, image upload, lightbox
 */

let API_BASE = '/api';
let sessionId = '';
let currentPage = 1;
let hasMore = false;
let isLoading = false;
let selectedImages = []; // File objects for upload

// ==================== HELPERS ====================

function getSessionId() {
    let id = localStorage.getItem('community_session_id');
    if (!id) {
        id = 'sess_' + Date.now() + '_' + Math.random().toString(36).substring(2, 10);
        localStorage.setItem('community_session_id', id);
    }
    return id;
}

function getSavedName() {
    return localStorage.getItem('community_author_name') || '';
}

function saveName(name) {
    if (name) localStorage.setItem('community_author_name', name);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(isoString) {
    const now = new Date();
    const date = new Date(isoString);
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'Vừa xong';
    if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} giờ trước`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} ngày trước`;
    return date.toLocaleDateString('vi-VN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function getInitial(name) {
    return name ? name.charAt(0).toUpperCase() : 'A';
}

// ==================== LOAD POSTS ====================

async function loadPosts(append = false) {
    if (isLoading) return;
    isLoading = true;

    try {
        const res = await fetch(`${API_BASE}/posts?page=${currentPage}&per_page=20&session_id=${sessionId}`);
        const data = await res.json();
        hasMore = data.has_more;

        const container = document.getElementById('posts-container');
        const emptyState = document.getElementById('empty-state');
        const loadMoreArea = document.getElementById('load-more-area');

        if (!append) container.innerHTML = '';

        if (data.posts.length === 0 && !append) {
            emptyState.classList.remove('hidden');
            loadMoreArea.classList.add('hidden');
        } else {
            emptyState.classList.add('hidden');
            data.posts.forEach(post => {
                container.appendChild(createPostCard(post));
            });
            if (hasMore) {
                loadMoreArea.classList.remove('hidden');
            } else {
                loadMoreArea.classList.add('hidden');
            }
        }
    } catch (err) {
        console.error('Failed to load posts:', err);
    } finally {
        isLoading = false;
    }
}

// ==================== POST CARD RENDERING ====================

function createPostCard(post) {
    const card = document.createElement('div');
    card.className = 'post-card';
    card.dataset.postId = post.id;

    const isLiked = post.liked_by.includes(sessionId);
    const isDisliked = post.disliked_by.includes(sessionId);

    let imagesHtml = '';
    if (post.images && post.images.length > 0) {
        const count = Math.min(post.images.length, 4);
        imagesHtml = `<div class="post-card__images post-card__images--${count}">`;
        post.images.slice(0, 4).forEach((src, i) => {
            imagesHtml += `<div class="post-card__image-item" data-index="${i}" data-images='${JSON.stringify(post.images)}'>
                <img src="${escapeHtml(src)}" alt="Post image" loading="lazy">
            </div>`;
        });
        imagesHtml += '</div>';
    }

    let locationHtml = '';
    if (post.location) {
        locationHtml = `<span class="dot"></span>
            <span class="post-card__location">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                ${escapeHtml(post.location)}
            </span>`;
    }

    const commentsHtml = post.comments.map(c => `
        <div class="comment-item">
            <div class="comment-item__avatar" style="background:${c.author_avatar_color}">${getInitial(c.author_name)}</div>
            <div>
                <div class="comment-item__body">
                    <div class="comment-item__author">${escapeHtml(c.author_name)}</div>
                    <div class="comment-item__text">${escapeHtml(c.content)}</div>
                </div>
                <div class="comment-item__time">${formatTime(c.created_at)}</div>
            </div>
        </div>
    `).join('');

    const isReported = post.reported_by && post.reported_by.includes(sessionId);

    card.innerHTML = `
        <div class="post-card__header">
            <div class="post-card__avatar" style="background:${post.author_avatar_color}">${getInitial(post.author_name)}</div>
            <div class="post-card__meta">
                <div class="post-card__author">${escapeHtml(post.author_name)}</div>
                <div class="post-card__info">
                    <span>${formatTime(post.created_at)}</span>
                    ${locationHtml}
                </div>
            </div>
            <button class="post-card__report-btn ${isReported ? 'post-card__report-btn--reported' : ''}" data-action="report" data-post-id="${post.id}" title="${isReported ? 'Đã báo cáo' : 'Báo cáo bài viết'}">
                <i class="fi fi-rr-flag-alt"></i>
            </button>
        </div>
        <div class="post-card__content">${escapeHtml(post.content)}</div>
        ${imagesHtml}
        <div class="post-card__actions">
            <button class="post-card__action-btn ${isLiked ? 'post-card__action-btn--liked' : ''}" data-action="like" data-post-id="${post.id}">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"/></svg>
                <span class="post-card__action-count">${post.likes || ''}</span>
            </button>
            <button class="post-card__action-btn ${isDisliked ? 'post-card__action-btn--disliked' : ''}" data-action="dislike" data-post-id="${post.id}">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.485.06L17 4m-7 10v2a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 9V4m-7 10h2m5-6h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5"/></svg>
                <span class="post-card__action-count">${post.dislikes || ''}</span>
            </button>
            <button class="post-card__action-btn" data-action="comment" data-post-id="${post.id}">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                <span class="post-card__action-count">${post.comments.length || ''}</span>
            </button>
        </div>
        <div class="post-card__comments" id="comments-${post.id}">
            <div class="post-card__comments-inner">
                <div class="comments-list">${commentsHtml}</div>
                <div class="comment-input-area">
                    <div class="comment-input-area__avatar">${getInitial(getSavedName() || 'B')}</div>
                    <input type="text" placeholder="Viết bình luận..." data-post-id="${post.id}" class="comment-input">
                    <button class="comment-input-area__send" data-post-id="${post.id}">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
                    </button>
                </div>
            </div>
        </div>
    `;

    return card;
}

// ==================== ACTIONS (LIKE / DISLIKE / COMMENT) ====================

async function handleLike(postId) {
    try {
        const res = await fetch(`${API_BASE}/posts/${postId}/like`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId }),
        });
        const post = await res.json();
        updatePostActions(postId, post);
    } catch (err) {
        console.error('Like failed:', err);
    }
}

async function handleDislike(postId) {
    try {
        const res = await fetch(`${API_BASE}/posts/${postId}/dislike`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId }),
        });
        const post = await res.json();
        updatePostActions(postId, post);
    } catch (err) {
        console.error('Dislike failed:', err);
    }
}

function updatePostActions(postId, post) {
    const card = document.querySelector(`.post-card[data-post-id="${postId}"]`);
    if (!card) return;

    const likeBtn = card.querySelector('[data-action="like"]');
    const dislikeBtn = card.querySelector('[data-action="dislike"]');

    if (likeBtn) {
        likeBtn.classList.toggle('post-card__action-btn--liked', post.liked_by.includes(sessionId));
        likeBtn.querySelector('.post-card__action-count').textContent = post.likes || '';
    }
    if (dislikeBtn) {
        dislikeBtn.classList.toggle('post-card__action-btn--disliked', post.disliked_by.includes(sessionId));
        dislikeBtn.querySelector('.post-card__action-count').textContent = post.dislikes || '';
    }
}

// ==================== REPORT ====================

async function handleReport(postId) {
    // Check if already reported
    const card = document.querySelector(`.post-card[data-post-id="${postId}"]`);
    const reportBtn = card?.querySelector('.post-card__report-btn');
    const isCurrentlyReported = reportBtn?.classList.contains('post-card__report-btn--reported');

    // Show appropriate confirmation dialog
    const confirmMessage = isCurrentlyReported
        ? 'Bạn có chắc muốn hủy báo cáo bài viết này?'
        : 'Bạn có chắc muốn báo cáo bài viết này?\nBài viết vi phạm sẽ bị ẩn sau khi nhận đủ báo cáo.';

    if (!confirm(confirmMessage)) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/posts/${postId}/report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, reason: 'Nội dung không phù hợp' }),
        });
        const data = await res.json();

        if (!res.ok) {
            showToast(data.error || 'Không thể thực hiện thao tác', 'error');
            return;
        }

        // Update button state based on action
        if (card && reportBtn) {
            if (data.action === 'unreported') {
                reportBtn.classList.remove('post-card__report-btn--reported');
                reportBtn.title = 'Báo cáo bài viết';
                showToast('Đã hủy báo cáo bài viết', 'info');
            } else {
                reportBtn.classList.add('post-card__report-btn--reported');
                reportBtn.title = 'Đã báo cáo';

                if (data.hidden) {
                    // Post reached threshold — remove from DOM
                    card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                    card.style.opacity = '0';
                    card.style.transform = 'scale(0.95)';
                    setTimeout(() => card.remove(), 300);
                    showToast('Bài viết đã bị ẩn do nhận nhiều báo cáo', 'info');
                } else {
                    showToast('Đã báo cáo bài viết. Cảm ơn bạn!', 'success');
                }
            }
        }
    } catch (err) {
        console.error('Report failed:', err);
        showToast('Lỗi khi báo cáo bài viết', 'error');
    }
}

function showToast(message, type = 'info') {
    // Remove existing toast
    const existing = document.querySelector('.community-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `community-toast community-toast--${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => toast.classList.add('community-toast--visible'));

    setTimeout(() => {
        toast.classList.remove('community-toast--visible');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function toggleComments(postId) {
    const section = document.getElementById(`comments-${postId}`);
    if (section) {
        section.classList.toggle('expanded');
        if (section.classList.contains('expanded')) {
            const input = section.querySelector('.comment-input');
            if (input) setTimeout(() => input.focus(), 350);
        }
    }
}

async function submitComment(postId) {
    const card = document.querySelector(`.post-card[data-post-id="${postId}"]`);
    const input = card?.querySelector('.comment-input');
    if (!input || !input.value.trim()) return;

    const content = input.value.trim();
    const authorName = getSavedName() || 'Người dùng ẩn danh';
    input.value = '';

    try {
        const res = await fetch(`${API_BASE}/posts/${postId}/comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, author_name: authorName, session_id: sessionId }),
        });
        const comment = await res.json();

        // Append comment to list
        const list = card.querySelector('.comments-list');
        if (list) {
            const div = document.createElement('div');
            div.className = 'comment-item';
            div.innerHTML = `
                <div class="comment-item__avatar" style="background:${comment.author_avatar_color}">${getInitial(comment.author_name)}</div>
                <div>
                    <div class="comment-item__body">
                        <div class="comment-item__author">${escapeHtml(comment.author_name)}</div>
                        <div class="comment-item__text">${escapeHtml(comment.content)}</div>
                    </div>
                    <div class="comment-item__time">Vừa xong</div>
                </div>
            `;
            list.appendChild(div);
        }

        // Update comment count
        const commentBtn = card.querySelector('[data-action="comment"] .post-card__action-count');
        if (commentBtn) {
            const current = parseInt(commentBtn.textContent) || 0;
            commentBtn.textContent = current + 1;
        }
    } catch (err) {
        console.error('Comment failed:', err);
    }
}

// ==================== CREATE POST MODAL ====================

function createModal() {
    const overlay = document.createElement('div');
    overlay.className = 'community-modal-overlay';
    overlay.id = 'create-post-modal';

    overlay.innerHTML = `
        <div class="community-modal">
            <div class="community-modal__header">
                <h4>Tạo bài viết</h4>
                <button class="community-modal__close" id="modal-close">&times;</button>
            </div>
            <div class="community-modal__body">
                <input type="text" class="community-modal__name-input" id="modal-author-name" placeholder="Tên của bạn" value="${escapeHtml(getSavedName())}">
                <textarea class="community-modal__textarea" id="modal-content" placeholder="Bạn đang nghĩ gì về giao thông?"></textarea>
                <div class="community-modal__image-upload" id="modal-image-upload">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                    <p>Thêm ảnh (tối đa 4)</p>
                    <span>JPG, PNG, GIF, WebP</span>
                </div>
                <input type="file" id="modal-image-input" accept="image/*" multiple style="display:none">
                <div class="community-modal__image-preview" id="modal-image-preview"></div>
                <input type="text" class="community-modal__location-input" id="modal-location" placeholder="Vị trí (tuỳ chọn)">
                <button class="community-modal__submit" id="modal-submit">Đăng bài viết</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    return overlay;
}

function openModal() {
    let modal = document.getElementById('create-post-modal');
    if (!modal) modal = createModal();
    selectedImages = [];
    updateImagePreview();

    // Reset fields
    const content = modal.querySelector('#modal-content');
    const location = modal.querySelector('#modal-location');
    if (content) content.value = '';
    if (location) location.value = '';

    // Update name from storage
    const nameInput = modal.querySelector('#modal-author-name');
    if (nameInput) nameInput.value = getSavedName();

    modal.classList.add('active');
    setTimeout(() => { if (content) content.focus(); }, 300);
    bindModalEvents(modal);
}

function closeModal() {
    const modal = document.getElementById('create-post-modal');
    if (modal) modal.classList.remove('active');
}

function bindModalEvents(modal) {
    // Close button
    modal.querySelector('#modal-close')?.addEventListener('click', closeModal);

    // Click overlay to close
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    // Image upload click
    modal.querySelector('#modal-image-upload')?.addEventListener('click', () => {
        modal.querySelector('#modal-image-input')?.click();
    });

    // File selected
    modal.querySelector('#modal-image-input')?.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        files.forEach(f => {
            if (selectedImages.length < 4) selectedImages.push(f);
        });
        updateImagePreview();
        e.target.value = '';
    });

    // Submit
    modal.querySelector('#modal-submit')?.addEventListener('click', handleCreatePost);
}

function updateImagePreview() {
    const preview = document.getElementById('modal-image-preview');
    const uploadArea = document.getElementById('modal-image-upload');
    if (!preview) return;

    preview.innerHTML = '';
    selectedImages.forEach((file, idx) => {
        const item = document.createElement('div');
        item.className = 'community-modal__image-preview-item';
        const img = document.createElement('img');
        img.src = URL.createObjectURL(file);
        const removeBtn = document.createElement('button');
        removeBtn.textContent = '\u00d7';
        removeBtn.addEventListener('click', () => {
            selectedImages.splice(idx, 1);
            updateImagePreview();
        });
        item.appendChild(img);
        item.appendChild(removeBtn);
        preview.appendChild(item);
    });

    if (uploadArea) {
        uploadArea.style.display = selectedImages.length >= 4 ? 'none' : '';
    }
}

async function handleCreatePost() {
    const modal = document.getElementById('create-post-modal');
    const content = modal.querySelector('#modal-content')?.value.trim();
    const authorName = modal.querySelector('#modal-author-name')?.value.trim();
    const location = modal.querySelector('#modal-location')?.value.trim();
    const submitBtn = modal.querySelector('#modal-submit');

    if (!content) return;
    if (authorName) saveName(authorName);

    submitBtn.disabled = true;
    submitBtn.textContent = 'Đang đăng...';

    try {
        const formData = new FormData();
        formData.append('content', content);
        formData.append('author_name', authorName || 'Người dùng ẩn danh');
        if (location) formData.append('location', location);
        selectedImages.forEach(f => formData.append('images', f));

        const res = await fetch(`${API_BASE}/posts`, { method: 'POST', body: formData });
        const data = await res.json();

        if (!res.ok) {
            showToast(data.error || 'Không thể đăng bài viết', 'error');
            return;
        }

        // Prepend new post to feed
        const container = document.getElementById('posts-container');
        const emptyState = document.getElementById('empty-state');
        if (container) {
            container.prepend(createPostCard(data));
        }
        if (emptyState) emptyState.classList.add('hidden');

        closeModal();
    } catch (err) {
        console.error('Create post failed:', err);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Đăng bài viết';
    }
}

// ==================== LIGHTBOX ====================

let lightboxImages = [];
let lightboxIndex = 0;

function createLightbox() {
    const overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.id = 'lightbox';

    overlay.innerHTML = `
        <button class="lightbox-close">&times;</button>
        <button class="lightbox-nav lightbox-nav--prev">&#8249;</button>
        <img src="" alt="Full size image">
        <button class="lightbox-nav lightbox-nav--next">&#8250;</button>
    `;

    overlay.querySelector('.lightbox-close').addEventListener('click', closeLightbox);
    overlay.querySelector('.lightbox-nav--prev').addEventListener('click', () => navigateLightbox(-1));
    overlay.querySelector('.lightbox-nav--next').addEventListener('click', () => navigateLightbox(1));
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeLightbox();
    });

    document.body.appendChild(overlay);
    return overlay;
}

function openLightbox(images, startIndex) {
    lightboxImages = images;
    lightboxIndex = startIndex;

    let lb = document.getElementById('lightbox');
    if (!lb) lb = createLightbox();

    updateLightboxImage(lb);
    lb.classList.add('active');

    // Show/hide nav buttons
    lb.querySelector('.lightbox-nav--prev').style.display = images.length > 1 ? '' : 'none';
    lb.querySelector('.lightbox-nav--next').style.display = images.length > 1 ? '' : 'none';
}

function closeLightbox() {
    const lb = document.getElementById('lightbox');
    if (lb) lb.classList.remove('active');
}

function navigateLightbox(dir) {
    lightboxIndex = (lightboxIndex + dir + lightboxImages.length) % lightboxImages.length;
    const lb = document.getElementById('lightbox');
    if (lb) updateLightboxImage(lb);
}

function updateLightboxImage(lb) {
    const img = lb.querySelector('img');
    if (img) img.src = lightboxImages[lightboxIndex];
}

// ==================== EVENT DELEGATION ====================

function setupEventListeners() {
    // Create post trigger
    document.getElementById('create-post-trigger')?.addEventListener('click', openModal);

    // Load more
    document.getElementById('load-more-btn')?.addEventListener('click', () => {
        currentPage++;
        loadPosts(true);
    });

    // Delegated events on posts container
    document.getElementById('posts-container')?.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (btn) {
            const action = btn.dataset.action;
            const postId = btn.dataset.postId;
            if (action === 'like') handleLike(postId);
            else if (action === 'dislike') handleDislike(postId);
            else if (action === 'comment') toggleComments(postId);
            else if (action === 'report') handleReport(postId);
            return;
        }

        // Image click -> lightbox
        const imageItem = e.target.closest('.post-card__image-item');
        if (imageItem) {
            try {
                const images = JSON.parse(imageItem.dataset.images);
                const index = parseInt(imageItem.dataset.index) || 0;
                openLightbox(images, index);
            } catch (err) {
                console.error('Lightbox error:', err);
            }
            return;
        }

        // Comment send button
        const sendBtn = e.target.closest('.comment-input-area__send');
        if (sendBtn) {
            submitComment(sendBtn.dataset.postId);
            return;
        }
    });

    // Enter key on comment input
    document.getElementById('posts-container')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.target.classList.contains('comment-input')) {
            e.preventDefault();
            submitComment(e.target.dataset.postId);
        }
    });

    // Keyboard shortcuts for lightbox
    document.addEventListener('keydown', (e) => {
        const lb = document.getElementById('lightbox');
        if (!lb || !lb.classList.contains('active')) return;
        if (e.key === 'Escape') closeLightbox();
        else if (e.key === 'ArrowLeft') navigateLightbox(-1);
        else if (e.key === 'ArrowRight') navigateLightbox(1);
    });

    // Escape to close modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.getElementById('create-post-modal');
            if (modal?.classList.contains('active')) closeModal();
        }
    });
}

// ==================== INIT ====================

export function initCommunity(apiBase) {
    API_BASE = apiBase || '/api';
    sessionId = getSessionId();

    // Update trigger avatar with saved name initial
    const triggerAvatar = document.getElementById('trigger-avatar');
    if (triggerAvatar) {
        triggerAvatar.textContent = getInitial(getSavedName() || 'B');
    }

    setupEventListeners();
    loadPosts();

    console.log('Community feed initialized');
}
