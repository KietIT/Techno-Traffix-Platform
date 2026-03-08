/**
 * Community Module v2 — Enhanced Social Feed
 * Features: Advanced filtering, real-time updates, search, categories, severity indicators
 */

let API_BASE = '/api';
let sessionId = '';
let currentPage = 1;
let hasMore = false;
let isLoading = false;
let selectedImages = [];
let allPosts = [];
let filteredPosts = [];
let activeFilters = {
    categories: [],
    time: 'all',
    sort: 'newest',
    search: ''
};
let pendingNewPosts = [];
let autoRefreshInterval = null;

// ==================== CONSTANTS ====================

const CATEGORIES = {
    accident: { label: 'Tai nạn', color: '#f43f5e', bgColor: 'rgba(244, 63, 94, 0.1)' },
    congestion: { label: 'Ùn tắc', color: '#f59e0b', bgColor: 'rgba(245, 158, 11, 0.1)' },
    roadwork: { label: 'Thi công', color: '#06b6d4', bgColor: 'rgba(6, 182, 212, 0.1)' },
    weather: { label: 'Thời tiết', color: '#8b5cf6', bgColor: 'rgba(139, 92, 246, 0.1)' },
    general: { label: 'Chung', color: '#64748b', bgColor: 'rgba(100, 116, 139, 0.1)' }
};

const SEVERITY = {
    low: { label: 'Thấp', icon: '🟢' },
    medium: { label: 'Trung bình', icon: '🟡' },
    high: { label: 'Cao', icon: '🔴' }
};

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

function getCategoryBadge(category, compact = false) {
    const cat = CATEGORIES[category] || CATEGORIES.general;
    if (compact) {
        return `
            <span class="post-card__tag-compact post-card__tag-compact--${category || 'general'}">
                ${cat.label}
            </span>
        `;
    }
    return `
        <span class="post-card__category-badge post-card__category-badge--${category || 'general'}" 
              style="background: ${cat.bgColor}; color: ${cat.color};">
            ${cat.label}
        </span>
    `;
}

function getSeverityIndicator(severity, compact = false) {
    if (!severity || severity === 'none') return '';
    const sev = SEVERITY[severity];
    if (compact) {
        return `
            <span class="post-card__severity-compact post-card__severity-compact--${severity}" 
                  title="Mức độ: ${sev.label}">
                ${sev.icon}
            </span>
        `;
    }
    return `
        <span class="post-card__severity post-card__severity--${severity}" title="Mức độ: ${sev.label}">
            ${sev.icon} ${sev.label}
        </span>
    `;
}

function getTagsRow(category, severity, hasImages) {
    // For posts without images, use compact inline tags
    if (!hasImages) {
        const cat = CATEGORIES[category] || CATEGORIES.general;
        const sev = severity && severity !== 'none' ? SEVERITY[severity] : null;

        let tagsHtml = '';

        // Category tag (compact inline style)
        tagsHtml += `
            <span class="post-card__tag-inline post-card__tag-inline--${category || 'general'}">
                ${cat.label}
            </span>
        `;

        // Severity indicator (if applicable)
        if (sev) {
            tagsHtml += `
                <span class="post-card__severity-inline post-card__severity-inline--${severity}" 
                      title="Mức độ: ${sev.label}">
                    ${sev.icon}
                </span>
            `;
        }

        return `<div class="post-card__tags-inline">${tagsHtml}</div>`;
    }

    // For posts with images, return empty (tags shown in standard format)
    return '';
}

// Get tag as colored hashtag to append to content
function getTagHashtag(category) {
    const cat = CATEGORIES[category] || CATEGORIES.general;
    // Create hashtag from category label (remove spaces and lowercase)
    const hashtag = '#' + cat.label.toLowerCase().replace(/\s+/g, '');

    return `<span class="post-card__hashtag post-card__hashtag--${category || 'general'}" 
                 style="color: ${cat.color}; font-weight: 600;">
        ${hashtag}
    </span>`;
}

// ==================== FILTERING & SEARCH ====================

function applyFilters() {
    filteredPosts = [...allPosts];

    // Filter by category
    if (activeFilters.categories.length > 0) {
        filteredPosts = filteredPosts.filter(post =>
            activeFilters.categories.includes(post.category || 'general')
        );
    }

    // Filter by time
    if (activeFilters.time !== 'all') {
        const now = new Date();
        const cutoffDate = new Date();

        switch (activeFilters.time) {
            case 'today':
                cutoffDate.setHours(0, 0, 0, 0);
                break;
            case 'week':
                cutoffDate.setDate(cutoffDate.getDate() - 7);
                break;
            case 'month':
                cutoffDate.setMonth(cutoffDate.getMonth() - 1);
                break;
        }

        filteredPosts = filteredPosts.filter(post =>
            new Date(post.created_at) >= cutoffDate
        );
    }

    // Filter by search
    if (activeFilters.search) {
        const searchLower = activeFilters.search.toLowerCase();
        filteredPosts = filteredPosts.filter(post =>
            post.content.toLowerCase().includes(searchLower) ||
            post.author_name.toLowerCase().includes(searchLower) ||
            (post.location && post.location.toLowerCase().includes(searchLower))
        );
    }

    // Sort
    switch (activeFilters.sort) {
        case 'newest':
            filteredPosts.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
            break;
        case 'popular':
            filteredPosts.sort((a, b) => (b.likes || 0) - (a.likes || 0));
            break;
        case 'discussed':
            filteredPosts.sort((a, b) => (b.comments?.length || 0) - (a.comments?.length || 0));
            break;
    }

    renderPosts();
    updateActiveFiltersDisplay();
}

function renderPosts() {
    const container = document.getElementById('posts-container');
    const emptyState = document.getElementById('empty-state');
    const noResultsState = document.getElementById('no-results-state');
    const loadMoreArea = document.getElementById('load-more-area');

    container.innerHTML = '';

    if (filteredPosts.length === 0) {
        if (allPosts.length === 0) {
            emptyState.classList.remove('hidden');
            noResultsState.classList.add('hidden');
        } else {
            emptyState.classList.add('hidden');
            noResultsState.classList.remove('hidden');
        }
        loadMoreArea.classList.add('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    noResultsState.classList.add('hidden');

    // Show first 20 posts, rest via load more
    const postsToShow = filteredPosts.slice(0, currentPage * 20);
    postsToShow.forEach(post => {
        container.appendChild(createPostCard(post));
    });

    hasMore = postsToShow.length < filteredPosts.length;
    if (hasMore) {
        loadMoreArea.classList.remove('hidden');
    } else {
        loadMoreArea.classList.add('hidden');
    }
}

function updateActiveFiltersDisplay() {
    const container = document.getElementById('active-filters');
    const tagsContainer = document.getElementById('active-filter-tags');

    const activeTags = [];

    // Category tags
    activeFilters.categories.forEach(cat => {
        activeTags.push({
            type: 'category',
            value: cat,
            label: CATEGORIES[cat]?.label || cat
        });
    });

    // Time tag
    if (activeFilters.time !== 'all') {
        const timeLabels = { today: 'Hôm nay', week: 'Tuần này', month: 'Tháng này' };
        activeTags.push({
            type: 'time',
            value: activeFilters.time,
            label: timeLabels[activeFilters.time]
        });
    }

    // Search tag
    if (activeFilters.search) {
        activeTags.push({
            type: 'search',
            value: activeFilters.search,
            label: `"${activeFilters.search}"`
        });
    }

    if (activeTags.length === 0) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    tagsContainer.innerHTML = activeTags.map(tag => `
        <div class="community-filter-tag">
            ${escapeHtml(tag.label)}
            <button onclick="window.communityRemoveFilter('${tag.type}', '${tag.value}')">×</button>
        </div>
    `).join('');
}

window.communityRemoveFilter = function (type, value) {
    if (type === 'category') {
        activeFilters.categories = activeFilters.categories.filter(c => c !== value);
        document.querySelector(`input[value="${value}"][data-filter="category"]`).checked = false;
    } else if (type === 'time') {
        activeFilters.time = 'all';
        document.querySelector('input[name="time-filter"][value="all"]').checked = true;
    } else if (type === 'search') {
        activeFilters.search = '';
        document.getElementById('community-search').value = '';
        document.getElementById('search-clear').classList.add('hidden');
    }
    applyFilters();
};

// ==================== LOAD POSTS ====================

async function loadPosts(append = false) {
    if (isLoading) return;
    isLoading = true;

    // Show skeleton on initial load
    if (!append) {
        document.getElementById('skeleton-container').classList.remove('hidden');
        document.getElementById('posts-container').innerHTML = '';
    }

    try {
        const res = await fetch(`${API_BASE}/posts?page=${currentPage}&per_page=20&session_id=${sessionId}`);
        const data = await res.json();

        if (!append) {
            allPosts = data.posts || [];
        } else {
            allPosts = [...allPosts, ...(data.posts || [])];
        }

        hasMore = data.has_more;

        // Update stats
        updateStats(data.stats || { total: allPosts.length, today: 0, active: 0 });

        // Hide skeleton
        document.getElementById('skeleton-container').classList.add('hidden');

        applyFilters();

    } catch (err) {
        console.error('Failed to load posts:', err);
        document.getElementById('skeleton-container').classList.add('hidden');
    } finally {
        isLoading = false;
    }
}

function updateStats(stats) {
    document.getElementById('stat-posts').textContent = stats.total || 0;
    document.getElementById('stat-today').textContent = stats.today || 0;
    document.getElementById('stat-active').textContent = stats.active || Math.floor(Math.random() * 50) + 10;
}

// ==================== POST CARD RENDERING ====================

function createPostCard(post) {
    const card = document.createElement('div');
    card.className = 'post-card';
    card.dataset.postId = post.id;

    const isLiked = post.liked_by.includes(sessionId);
    const isDisliked = post.disliked_by.includes(sessionId);

    // Check if post has images
    const hasImages = post.images && post.images.length > 0;

    // For text-only posts, use compact inline tags
    // For posts with images, use standard badge format
    const categoryBadge = hasImages ? getCategoryBadge(post.category) : '';
    const severityIndicator = hasImages ? getSeverityIndicator(post.severity) : '';
    const inlineTags = getTagsRow(post.category, post.severity, hasImages);

    let imagesHtml = '';
    if (hasImages) {
        const count = Math.min(post.images.length, 4);
        imagesHtml = `<div class="post-card__images post-card__images--${count}">`;
        post.images.slice(0, 4).forEach((src, i) => {
            imagesHtml += `
                <div class="post-card__image-item" data-index="${i}" data-images='${JSON.stringify(post.images)}'>
                    <img src="${escapeHtml(src)}" alt="Post image" loading="lazy">
                    ${i === 3 && post.images.length > 4 ? `
                        <div class="post-card__image-counter">+${post.images.length - 4}</div>
                    ` : ''}
                </div>
            `;
        });
        imagesHtml += '</div>';
    }

    let locationHtml = '';
    if (post.location) {
        locationHtml = `<span class="dot"></span>
            <span class="post-card__location">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                </svg>
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
    const commentCount = post.comments?.length || 0;

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
            <button class="post-card__report-btn ${isReported ? 'post-card__report-btn--reported' : ''}" 
                    data-action="report" data-post-id="${post.id}" 
                    title="${isReported ? 'Đã báo cáo' : 'Báo cáo bài viết'}">
                <i class="fi fi-rr-flag-alt"></i>
            </button>
        </div>
        <div class="post-card__content">
            <div class="post-card__text-content">${escapeHtml(post.content)} ${getTagHashtag(post.category)}</div>
        </div>
        ${imagesHtml}
        <div class="post-card__actions">
            <button class="post-card__action-btn ${isLiked ? 'post-card__action-btn--liked' : ''}" 
                    data-action="like" data-post-id="${post.id}" aria-pressed="${isLiked}">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"/>
                </svg>
                <span class="post-card__action-count">${post.likes || ''}</span>
            </button>
            <button class="post-card__action-btn ${isDisliked ? 'post-card__action-btn--disliked' : ''}" 
                    data-action="dislike" data-post-id="${post.id}" aria-pressed="${isDisliked}">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.485.06L17 4m-7 10v2a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 9V4m-7 10h2m5-6h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5"/>
                </svg>
                <span class="post-card__action-count">${post.dislikes || ''}</span>
            </button>
            <button class="post-card__action-btn" data-action="comment" data-post-id="${post.id}">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
                <span class="post-card__action-count">${commentCount || ''}</span>
            </button>
        </div>
        ${commentCount > 0 ? `
            <div class="post-card__comments-preview">
                <span class="comments-preview__count" onclick="window.communityToggleComments('${post.id}')">
                    Xem ${commentCount} bình luận
                </span>
            </div>
        ` : ''}
        <div class="post-card__comments" id="comments-${post.id}">
            <div class="post-card__comments-inner">
                <div class="comments-list">${commentsHtml}</div>
                <div class="comment-input-area">
                    <div class="comment-input-area__avatar">${getInitial(getSavedName() || 'B')}</div>
                    <input type="text" placeholder="Viết bình luận..." data-post-id="${post.id}" class="comment-input">
                    <button class="comment-input-area__send" data-post-id="${post.id}">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `;

    return card;
}

window.communityToggleComments = function (postId) {
    toggleComments(postId);
};

// ==================== ACTIONS ====================

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
        const liked = post.liked_by.includes(sessionId);
        likeBtn.classList.toggle('post-card__action-btn--liked', liked);
        likeBtn.setAttribute('aria-pressed', String(liked));
        likeBtn.querySelector('.post-card__action-count').textContent = post.likes || '';
    }
    if (dislikeBtn) {
        const disliked = post.disliked_by.includes(sessionId);
        dislikeBtn.classList.toggle('post-card__action-btn--disliked', disliked);
        dislikeBtn.setAttribute('aria-pressed', String(disliked));
        dislikeBtn.querySelector('.post-card__action-count').textContent = post.dislikes || '';
    }
}

async function handleReport(postId) {
    const card = document.querySelector(`.post-card[data-post-id="${postId}"]`);
    const reportBtn = card?.querySelector('.post-card__report-btn');
    const isCurrentlyReported = reportBtn?.classList.contains('post-card__report-btn--reported');

    const confirmMessage = isCurrentlyReported
        ? 'Bạn có chắc muốn hủy báo cáo bài viết này?'
        : 'Bạn có chắc muốn báo cáo bài viết này?\nBài viết vi phạm sẽ bị ẩn sau khi nhận đủ báo cáo.';

    if (!confirm(confirmMessage)) return;

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

        if (card && reportBtn) {
            if (data.action === 'unreported') {
                reportBtn.classList.remove('post-card__report-btn--reported');
                reportBtn.title = 'Báo cáo bài viết';
                showToast('Đã hủy báo cáo bài viết', 'info');
            } else {
                reportBtn.classList.add('post-card__report-btn--reported');
                reportBtn.title = 'Đã báo cáo';

                if (data.hidden) {
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
    const existing = document.querySelector('.community-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `community-toast community-toast--${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

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
                <input type="text" class="community-modal__name-input" id="modal-author-name" 
                       placeholder="Tên của bạn" value="${escapeHtml(getSavedName())}">
                
                <!-- Category Selection -->
                <div class="community-modal__category-select">
                    <label class="community-modal__label">Loại sự cố:</label>
                    <div class="community-modal__categories">
                        ${Object.entries(CATEGORIES).map(([key, cat]) => `
                            <label class="community-modal__category-option">
                                <input type="radio" name="category" value="${key}" ${key === 'general' ? 'checked' : ''}>
                                <span style="background: ${cat.bgColor}; color: ${cat.color};">${cat.label}</span>
                            </label>
                        `).join('')}
                    </div>
                </div>
                
                <!-- Severity Selection (for accident/congestion) -->
                <div class="community-modal__severity-select" id="severity-select-container" style="display: none;">
                    <label class="community-modal__label">Mức độ nghiêm trọng:</label>
                    <div class="community-modal__severities">
                        ${Object.entries(SEVERITY).map(([key, sev]) => `
                            <label class="community-modal__severity-option">
                                <input type="radio" name="severity" value="${key}" ${key === 'low' ? 'checked' : ''}>
                                <span>${sev.icon} ${sev.label}</span>
                            </label>
                        `).join('')}
                    </div>
                </div>
                
                <textarea class="community-modal__textarea" id="modal-content" 
                          placeholder="Mô tả tình hình giao thông..."></textarea>
                
                <div class="community-modal__image-upload" id="modal-image-upload">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2z"/>
                    </svg>
                    <p>Thêm ảnh (tối đa 4)</p>
                    <span>Kéo thả hoặc nhấn để chọn</span>
                </div>
                <input type="file" id="modal-image-input" accept="image/*" multiple style="display:none">
                <div class="community-modal__image-preview" id="modal-image-preview"></div>
                
                <div class="community-modal__location-row">
                    <input type="text" class="community-modal__location-input" id="modal-location"
                           placeholder="📍 Vị trí (tuỳ chọn)">
                    <button type="button" class="community-modal__gps-btn" id="modal-gps-btn" title="Lấy vị trí GPS hiện tại">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="18" height="18">
                            <circle cx="12" cy="12" r="3" stroke-width="2"/>
                            <path stroke-linecap="round" stroke-width="2" d="M12 2v3m0 14v3M2 12h3m14 0h3"/>
                            <circle cx="12" cy="12" r="8" stroke-width="2"/>
                        </svg>
                    </button>
                </div>
                
                <button class="community-modal__submit" id="modal-submit">Đăng bài viết</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    return overlay;
}

// Step 7: Keyboard-aware modal height adjustment
let _viewportHandler = null;

// Focus trap for create-post modal (P2.7)
let _communityTrapHandler = null;
let _communityPreviousFocus = null;

function _setupCommunityFocusTrap(modal) {
    _removeCommunityFocusTrap();
    const container = modal.querySelector('.community-modal');
    if (!container) return;

    _communityTrapHandler = (e) => {
        if (e.key !== 'Tab') return;
        const focusable = container.querySelectorAll(
            'input:not([disabled]):not([style*="display:none"]), ' +
            'textarea:not([disabled]), ' +
            'button:not([disabled]), ' +
            'select:not([disabled]), ' +
            '[tabindex]:not([tabindex="-1"]):not([disabled])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
            if (document.activeElement === first) {
                e.preventDefault();
                last.focus();
            }
        } else {
            if (document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    };
    document.addEventListener('keydown', _communityTrapHandler);
}

function _removeCommunityFocusTrap() {
    if (_communityTrapHandler) {
        document.removeEventListener('keydown', _communityTrapHandler);
        _communityTrapHandler = null;
    }
}

function setupModalKeyboardHandling(modal) {
    if (!isMobileQuery.matches || !window.visualViewport) return;

    const modalEl = modal.querySelector('.community-modal');
    if (!modalEl) return;

    _viewportHandler = () => {
        const vv = window.visualViewport;
        const keyboardHeight = window.innerHeight - vv.height;

        if (keyboardHeight > 100) {
            // Keyboard is open — shrink modal to fit above it
            modalEl.style.maxHeight = `${vv.height - 20}px`;
            // Scroll the focused input into view
            const focused = modal.querySelector(':focus');
            if (focused) {
                setTimeout(() => focused.scrollIntoView({ block: 'center', behavior: 'smooth' }), 50);
            }
        } else {
            // Keyboard closed — restore
            modalEl.style.maxHeight = '';
        }
    };

    window.visualViewport.addEventListener('resize', _viewportHandler);
}

function teardownModalKeyboardHandling() {
    if (_viewportHandler && window.visualViewport) {
        window.visualViewport.removeEventListener('resize', _viewportHandler);
        _viewportHandler = null;
    }
}

function openModal() {
    let modal = document.getElementById('create-post-modal');
    if (!modal) modal = createModal();
    selectedImages = [];
    updateImagePreview();

    const content = modal.querySelector('#modal-content');
    const location = modal.querySelector('#modal-location');
    if (content) content.value = '';
    if (location) location.value = '';

    const nameInput = modal.querySelector('#modal-author-name');
    if (nameInput) nameInput.value = getSavedName();

    modal.classList.add('community-modal-overlay--open');
    _communityPreviousFocus = document.activeElement;
    setTimeout(() => { if (content) content.focus(); }, 300);
    bindModalEvents(modal);
    _setupCommunityFocusTrap(modal);

    // Step 7: Enable keyboard-aware resizing on mobile
    setupModalKeyboardHandling(modal);
}

function closeModal() {
    const modal = document.getElementById('create-post-modal');
    if (modal) {
        modal.classList.remove('community-modal-overlay--open');
        _removeCommunityFocusTrap();
        // Step 7: Clean up keyboard handler
        teardownModalKeyboardHandling();
        const modalEl = modal.querySelector('.community-modal');
        if (modalEl) modalEl.style.maxHeight = '';
    }
    // Restore previous focus
    if (_communityPreviousFocus && _communityPreviousFocus.focus) {
        _communityPreviousFocus.focus();
        _communityPreviousFocus = null;
    }
}

async function handleGPSLocation() {
    const btn = document.getElementById('modal-gps-btn');
    const locationInput = document.getElementById('modal-location');
    if (!btn || !locationInput) return;

    if (!navigator.geolocation) {
        showToast('Trình duyệt không hỗ trợ GPS', 'error');
        return;
    }

    btn.classList.add('loading');
    btn.disabled = true;

    try {
        const position = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000
            });
        });

        const { latitude, longitude } = position.coords;

        // Reverse geocode via Nominatim
        const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json&accept-language=vi`,
            { headers: { 'User-Agent': 'TechnoTraffixApp/1.0' } }
        );

        if (res.ok) {
            const data = await res.json();
            const addr = data.address;
            // Build a concise Vietnamese-friendly address
            const parts = [addr.road, addr.suburb || addr.quarter, addr.city || addr.town || addr.county, addr.state].filter(Boolean);
            locationInput.value = parts.join(', ') || data.display_name || `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
        } else {
            locationInput.value = `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
        }

        showToast('Đã lấy vị trí GPS thành công', 'success');
    } catch (err) {
        const messages = {
            1: 'Bạn đã từ chối quyền truy cập vị trí',
            2: 'Không thể xác định vị trí hiện tại',
            3: 'Hết thời gian chờ lấy vị trí'
        };
        showToast(messages[err.code] || 'Không thể lấy vị trí GPS', 'error');
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

function bindModalEvents(modal) {
    modal.querySelector('#modal-close')?.addEventListener('click', closeModal);
    modal.querySelector('#modal-gps-btn')?.addEventListener('click', handleGPSLocation);

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    // Category change - show/hide severity
    const categoryInputs = modal.querySelectorAll('input[name="category"]');
    const severityContainer = modal.querySelector('#severity-select-container');

    categoryInputs.forEach(input => {
        input.addEventListener('change', () => {
            const showSeverity = ['accident', 'congestion'].includes(input.value);
            severityContainer.style.display = showSeverity ? 'block' : 'none';
        });
    });

    // Image upload
    modal.querySelector('#modal-image-upload')?.addEventListener('click', () => {
        modal.querySelector('#modal-image-input')?.click();
    });

    // Drag and drop
    const uploadArea = modal.querySelector('#modal-image-upload');
    uploadArea?.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea?.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea?.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = Array.from(e.dataTransfer.files);
        files.forEach(f => {
            if (selectedImages.length < 4 && f.type.startsWith('image/')) selectedImages.push(f);
        });
        updateImagePreview();
    });

    modal.querySelector('#modal-image-input')?.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        files.forEach(f => {
            if (selectedImages.length < 4) selectedImages.push(f);
        });
        updateImagePreview();
        e.target.value = '';
    });

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
        removeBtn.textContent = '×';
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
    const category = modal.querySelector('input[name="category"]:checked')?.value || 'general';
    const severity = modal.querySelector('input[name="severity"]:checked')?.value || 'none';
    const submitBtn = modal.querySelector('#modal-submit');

    if (!content) {
        showToast('Vui lòng nhập nội dung bài viết', 'error');
        return;
    }

    // Validation: Must have image OR location (or both)
    if (selectedImages.length === 0 && !location) {
        showToast('Vui lòng thêm ảnh hoặc địa điểm cụ thể để đăng bài', 'error');
        return;
    }

    if (authorName) saveName(authorName);

    submitBtn.disabled = true;
    submitBtn.textContent = 'Đang đăng...';

    try {
        const formData = new FormData();
        formData.append('content', content);
        formData.append('author_name', authorName || 'Người dùng ẩn danh');
        formData.append('category', category);
        formData.append('severity', severity);
        if (location) formData.append('location', location);
        selectedImages.forEach(f => formData.append('images', f));

        const res = await fetch(`${API_BASE}/posts`, { method: 'POST', body: formData });
        const data = await res.json();

        if (!res.ok) {
            showToast(data.error || 'Không thể đăng bài viết', 'error');
            return;
        }

        allPosts.unshift(data);
        applyFilters();

        document.getElementById('empty-state')?.classList.add('hidden');
        showToast('Đã đăng bài viết thành công!', 'success');
        closeModal();
    } catch (err) {
        console.error('Create post failed:', err);
        showToast('Lỗi khi đăng bài viết', 'error');
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

// ==================== REAL-TIME UPDATES ====================

function startAutoRefresh() {
    // Check for new posts every 30 seconds
    autoRefreshInterval = setInterval(checkForNewPosts, 30000);
}

async function checkForNewPosts() {
    // Skip if community tab is not active — avoid unnecessary fetches every 30s
    const communityPanel = document.getElementById('tab-community');
    if (!communityPanel || !communityPanel.classList.contains('tab-panel--active')) return;

    try {
        const res = await fetch(`${API_BASE}/posts?session_id=${sessionId}&since=${allPosts[0]?.created_at || ''}`);
        const data = await res.json();

        if (data.posts && data.posts.length > 0) {
            const newPosts = data.posts.filter(p => !allPosts.find(ep => ep.id === p.id));
            if (newPosts.length > 0) {
                pendingNewPosts = [...pendingNewPosts, ...newPosts];
                showNewPostsNotification(pendingNewPosts.length);
            }
        }
    } catch (err) {
        console.error('Auto-refresh failed:', err);
    }
}

function showNewPostsNotification(count) {
    const notif = document.getElementById('new-posts-notif');
    const countEl = document.getElementById('new-posts-count');

    if (notif && countEl) {
        countEl.textContent = count;
        notif.classList.remove('hidden');
    }
}

function loadNewPosts() {
    if (pendingNewPosts.length === 0) return;

    allPosts = [...pendingNewPosts, ...allPosts];
    pendingNewPosts = [];

    document.getElementById('new-posts-notif').classList.add('hidden');
    applyFilters();

    // Scroll to top
    const container = document.getElementById('community-feed');
    if (container) {
        container.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

// ==================== FILTER UI EVENTS ====================

function setupFilterEvents() {
    // Search
    const searchInput = document.getElementById('community-search');
    const searchClear = document.getElementById('search-clear');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            activeFilters.search = e.target.value.trim();
            searchClear.classList.toggle('hidden', !activeFilters.search);
            applyFilters();
        });
    }

    if (searchClear) {
        searchClear.addEventListener('click', () => {
            searchInput.value = '';
            activeFilters.search = '';
            searchClear.classList.add('hidden');
            applyFilters();
        });
    }

    // Category filter
    document.querySelectorAll('input[data-filter="category"]').forEach(input => {
        input.addEventListener('change', () => {
            activeFilters.categories = Array.from(document.querySelectorAll('input[data-filter="category"]:checked'))
                .map(cb => cb.value);
            applyFilters();
        });
    });

    // Time filter
    document.querySelectorAll('input[data-filter="time"]').forEach(input => {
        input.addEventListener('change', () => {
            activeFilters.time = input.value;
            applyFilters();
        });
    });

    // Sort
    document.querySelectorAll('input[data-sort="true"]').forEach(input => {
        input.addEventListener('change', () => {
            activeFilters.sort = input.value;
            applyFilters();
        });
    });

    // Clear all filters
    document.getElementById('clear-all-filters')?.addEventListener('click', () => {
        activeFilters = {
            categories: [],
            time: 'all',
            sort: 'newest',
            search: ''
        };

        // Reset UI
        document.querySelectorAll('input[data-filter="category"]').forEach(cb => cb.checked = false);
        document.querySelector('input[value="all"][data-filter="time"]').checked = true;
        document.querySelector('input[value="newest"][data-sort="true"]').checked = true;
        document.getElementById('community-search').value = '';
        document.getElementById('search-clear').classList.add('hidden');

        applyFilters();
    });

    // Load new posts
    document.getElementById('load-new-posts')?.addEventListener('click', loadNewPosts);

    // Clear search button in no results
    document.getElementById('clear-search-btn')?.addEventListener('click', () => {
        document.getElementById('clear-all-filters').click();
    });

    // Dropdown toggles
    setupDropdownToggle('filter-category-btn', 'filter-category-menu');
    setupDropdownToggle('filter-time-btn', 'filter-time-menu');
    setupDropdownToggle('sort-btn', 'sort-menu');
}

// Mobile detection helper
const isMobileQuery = window.matchMedia('(max-width: 768px)');

function getOrCreateBackdrop() {
    let backdrop = document.querySelector('.community-filter-backdrop');
    if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.className = 'community-filter-backdrop';
        document.body.appendChild(backdrop);
    }
    return backdrop;
}

function closeAllDropdowns() {
    document.querySelectorAll('.community-filter-dropdown__menu.active').forEach(m => {
        m.classList.remove('active');
        m.previousElementSibling?.classList.remove('active');
        m.closest('.community-filter-dropdown')?.classList.remove('active');
    });
    const backdrop = document.querySelector('.community-filter-backdrop');
    if (backdrop) backdrop.classList.remove('active');
}

function setupDropdownToggle(btnId, menuId) {
    const btn = document.getElementById(btnId);
    const menu = document.getElementById(menuId);

    if (!btn || !menu) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();

        const wasActive = menu.classList.contains('active');

        // Close other menus
        closeAllDropdowns();

        if (!wasActive) {
            menu.classList.add('active');
            btn.classList.add('active');
            btn.closest('.community-filter-dropdown')?.classList.add('active');

            // Step 6: Show backdrop on mobile
            if (isMobileQuery.matches) {
                const backdrop = getOrCreateBackdrop();
                backdrop.classList.add('active');
                backdrop.onclick = () => closeAllDropdowns();
            }
        }
    });

    // Close on outside click
    document.addEventListener('click', () => {
        menu.classList.remove('active');
        btn.classList.remove('active');
        btn.closest('.community-filter-dropdown')?.classList.remove('active');
        const backdrop = document.querySelector('.community-filter-backdrop');
        if (backdrop) backdrop.classList.remove('active');
    });

    // Prevent menu click from closing
    menu.addEventListener('click', (e) => {
        if (e.target.closest('.community-filter-option')) {
            setTimeout(() => {
                closeAllDropdowns();
            }, 150);
        } else {
            e.stopPropagation();
        }
    });
}

// ==================== EVENT DELEGATION ====================

function setupEventListeners() {
    // Create post triggers
    document.getElementById('create-post-trigger')?.addEventListener('click', openModal);
    document.getElementById('create-post-trigger-v2')?.addEventListener('click', openModal);

    // Load more
    document.getElementById('load-more-btn')?.addEventListener('click', () => {
        currentPage++;
        renderPosts();
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

        const sendBtn = e.target.closest('.comment-input-area__send');
        if (sendBtn) {
            submitComment(sendBtn.dataset.postId);
            return;
        }
    });

    document.getElementById('posts-container')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.target.classList.contains('comment-input')) {
            e.preventDefault();
            submitComment(e.target.dataset.postId);
        }
    });

    document.addEventListener('keydown', (e) => {
        const lb = document.getElementById('lightbox');
        if (!lb || !lb.classList.contains('active')) return;
        if (e.key === 'Escape') closeLightbox();
        else if (e.key === 'ArrowLeft') navigateLightbox(-1);
        else if (e.key === 'ArrowRight') navigateLightbox(1);
    });

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

    // Update trigger avatars
    const initial = getInitial(getSavedName() || 'B');
    const triggerAvatar = document.getElementById('trigger-avatar');
    const triggerAvatarV2 = document.getElementById('trigger-avatar-v2');
    if (triggerAvatar) triggerAvatar.textContent = initial;
    if (triggerAvatarV2) triggerAvatarV2.textContent = initial;

    setupEventListeners();
    setupFilterEvents();
    loadPosts();
    startAutoRefresh();

    console.log('Community feed v2 initialized');
}
