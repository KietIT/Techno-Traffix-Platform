/**
 * Tabs Module - Handle navigation tab switching with Floating Indicator
 * 
 * Hệ thống Tab với 3 phần:
 * 
 * A. NAVIGATION INDICATOR (Thanh trượt trên menu)
 *    1. Menu cha (nav) = relative -> làm "mốc" cho indicator
 *    2. Indicator = absolute -> di chuyển tự do trong nav
 *    3. Hover: Indicator di chuyển theo tab đang hover
 *    4. Active: Khi click, ghi nhớ tab active. Khi rời chuột, quay về tab active
 * 
 * B. TAB PANELS (Nội dung các tab)
 *    1. Container = relative -> Khung chứa cố định
 *    2. Panels = absolute -> Các khối nội dung đè lên nhau tại cùng vị trí
 *    3. Trạng thái ẩn: opacity: 0, transform: translateY(20px)
 *    4. Trạng thái hiện: opacity: 1, transform: translateY(0)
 *    5. Transition với ease-in-out để chuyển cảnh mượt mà
 * 
 * C. FULL PAGE MODE
 *    1. Tab Overview: Hiển thị Hero section + Tab content bên dưới
 *    2. Tab khác: Ẩn Hero section, Tab content hiển thị full page
 */

export function initTabs() {
    const nav = document.getElementById('main-nav');
    const tabs = document.querySelectorAll('.nav-tab');
    const tabPanels = document.querySelectorAll('.tab-panel');
    const tabPanelsContainer = document.querySelector('.tab-panels-container');
    const mobileToggle = document.getElementById('mobile-menu-toggle');
    const heroButtons = document.querySelectorAll('.hero__actions .btn[data-tab]');

    // Elements cho full page mode
    const heroSection = document.getElementById('hero-section');
    const mainContent = document.getElementById('main-content');
    const logoLink = document.querySelector('.header__logo');

    // Lưu trữ tab đang active
    let activeTabName = 'overview';
    let currentPanel = null;

    // ==================== HELPER FUNCTIONS ====================

    /**
     * Lấy tab element từ tên tab
     */
    function getTabElement(tabName) {
        return document.querySelector(`.nav-tab[data-tab="${tabName}"]`);
    }

    // ==================== FULL PAGE MODE ====================

    /**
     * Cập nhật layout dựa trên tab đang active
     * - Overview: Hiển thị hero, main content nằm dưới
     * - Các tab khác: Ẩn hero, main content full page
     */
    function updatePageLayout(tabName) {
        const isOverview = tabName === 'overview';

        if (heroSection) {
            if (isOverview) {
                // Hiển thị hero section
                heroSection.classList.remove('hero--hidden');
            } else {
                // Ẩn hero section
                heroSection.classList.add('hero--hidden');
            }
        }

        if (mainContent) {
            if (isOverview) {
                mainContent.classList.remove('main-content--fullpage');
            } else {
                mainContent.classList.add('main-content--fullpage');
            }
        }
    }

    // ==================== TAB PANELS TRANSITION ====================

    /**
     * Cập nhật chiều cao container dựa trên panel đang active
     * Tránh hiện tượng "giật" trang khi nội dung thay đổi
     */
    function updateContainerHeight(panel) {
        if (!tabPanelsContainer || !panel) return;

        // Nếu là tab overview, không cần set min-height
        if (panel.id === 'tab-overview') {
            tabPanelsContainer.style.minHeight = '0';
            return;
        }

        // Đợi một chút để panel render xong
        requestAnimationFrame(() => {
            const panelHeight = panel.scrollHeight;
            tabPanelsContainer.style.minHeight = `${Math.max(panelHeight, 400)}px`;
        });
    }

    /**
     * Chuyển đổi tab panel với hiệu ứng cross-fade
     * @param {string} tabName - Tên tab cần chuyển đến
     */
    function switchPanel(tabName) {
        const targetId = `tab-${tabName}`;
        const targetPanel = document.getElementById(targetId);

        if (!targetPanel) return;

        // Bước 1: Xóa trạng thái active từ tất cả panels
        tabPanels.forEach(panel => {
            if (panel.classList.contains('tab-panel--active')) {
                // Thêm class leaving cho hiệu ứng fade-out
                panel.classList.add('tab-panel--leaving');
            }
            panel.classList.remove('tab-panel--active');
        });

        // Bước 2: Kích hoạt panel mới (với delay nhỏ để tạo hiệu ứng cross-fade)
        setTimeout(() => {
            // Xóa class leaving khỏi tất cả panels
            tabPanels.forEach(panel => {
                panel.classList.remove('tab-panel--leaving');
            });

            // Thêm class active vào panel mới
            targetPanel.classList.add('tab-panel--active');

            // Cập nhật chiều cao container
            updateContainerHeight(targetPanel);

            // Lưu reference đến panel hiện tại
            currentPanel = targetPanel;
        }, 100); // Delay 100ms để tạo hiệu ứng cross-fade mượt
    }

    /**
     * Chuyển đổi tab hoàn chỉnh (cả navigation và content)
     */
    function switchToTab(tabName) {
        // Nếu đang ở tab này rồi thì không làm gì
        if (tabName === activeTabName) return;

        // Cập nhật active tab name
        activeTabName = tabName;

        // === PAGE LAYOUT ===
        // Cập nhật layout (ẩn/hiện hero section)
        updatePageLayout(tabName);

        // === NAVIGATION ===
        // Remove active state from all nav tabs
        tabs.forEach(t => t.classList.remove('nav-tab--active'));

        // Add active state to clicked tab
        const activeTab = getTabElement(tabName);
        if (activeTab) {
            activeTab.classList.add('nav-tab--active');
        }

        // === CONTENT PANELS ===
        switchPanel(tabName);

        // === SIDE EFFECTS ===

        // Close mobile menu after selection
        if (nav) {
            nav.classList.remove('header__nav--open');
        }

        // Initialize maps if switching to map tabs
        if (tabName === 'traffic' || tabName === 'air') {
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
            }, 600); // Đợi animation hoàn tất
        }

        // Smooth scroll to top khi chuyển tab (không phải overview)
        if (tabName !== 'overview') {
            setTimeout(() => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }, 100);
        }

        // Update URL hash without scrolling
        history.pushState(null, null, `#${tabName}`);
    }

    // ==================== EVENT LISTENERS ====================

    // Tab click handling
    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            switchToTab(tab.dataset.tab);
        });
    });

    // Logo click - Return to overview tab
    if (logoLink) {
        logoLink.addEventListener('click', (e) => {
            e.preventDefault();
            switchToTab('overview');
        });
    }

    // Hero button click handling (for "Kham pha Nen tang" and "Tim hieu them")
    heroButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            switchToTab(btn.dataset.tab);
        });
    });

    // Mobile menu toggle
    if (mobileToggle && nav) {
        mobileToggle.addEventListener('click', () => {
            nav.classList.toggle('header__nav--open');
        });

        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!nav.contains(e.target) && !mobileToggle.contains(e.target)) {
                nav.classList.remove('header__nav--open');
            }
        });
    }

    // Handle anchor links from URL
    const handleHashChange = () => {
        const hash = window.location.hash.replace('#', '');
        if (hash) {
            const targetTab = getTabElement(hash);
            if (targetTab) {
                // Dùng setTimeout để đảm bảo DOM đã sẵn sàng
                setTimeout(() => switchToTab(hash), 100);
            }
        }
    };

    window.addEventListener('hashchange', handleHashChange);

    // Update indicator và container height on window resize
    window.addEventListener('resize', () => {
        const activeTab = getTabElement(activeTabName);
        if (activeTab) {
            moveIndicatorTo(activeTab, false);
        }

        // Cập nhật chiều cao container
        if (currentPanel) {
            updateContainerHeight(currentPanel);
        }
    });

    // ==================== INITIALIZATION ====================

    // Initialize after DOM is ready
    setTimeout(() => {
        // Khởi tạo panel đầu tiên
        const initialPanel = document.getElementById(`tab-${activeTabName}`);
        if (initialPanel) {
            currentPanel = initialPanel;
            updateContainerHeight(initialPanel);
        }

        // Khởi tạo layout ban đầu
        updatePageLayout(activeTabName);

        // Mark initial active tab
        const activeTab = getTabElement(activeTabName);
        if (activeTab) {
            activeTab.classList.add('nav-tab--active');
        }
    }, 50);

    // Handle initial hash on page load
    if (window.location.hash) {
        handleHashChange();
    }

    console.log('Navigation tabs with floating indicator, smooth panel transitions, and full-page mode initialized');
}
