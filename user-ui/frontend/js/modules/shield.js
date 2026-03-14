/**
 * Shield Module - Source code viewing deterrent
 * Disables common methods of inspecting page source on desktop browsers.
 * Does NOT affect core functionality: inputs, links, buttons, maps all work normally.
 */

export function initShield() {
    if (isMobileDevice()) return; // Skip on mobile — no DevTools threat

    blockContextMenu();
    blockDevToolsShortcuts();
    blockDragEvents();
    warnConsole();
    detectDevTools();
}

/**
 * Block right-click context menu on the page.
 * Allows right-click inside input/textarea so users can still paste.
 */
function blockContextMenu() {
    document.addEventListener('contextmenu', (e) => {
        const tag = e.target.tagName;
        // Allow context menu on form fields for paste/spellcheck
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;
        e.preventDefault();
    });
}

/**
 * Block keyboard shortcuts that open DevTools or View Source.
 * Intercepted keys:
 *   F12                → DevTools
 *   Ctrl+Shift+I       → DevTools (Elements)
 *   Ctrl+Shift+J       → DevTools (Console)
 *   Ctrl+Shift+C       → DevTools (Inspect element)
 *   Ctrl+U             → View Page Source
 *   Ctrl+S             → Save Page
 */
function blockDevToolsShortcuts() {
    document.addEventListener('keydown', (e) => {
        // F12
        if (e.key === 'F12') {
            e.preventDefault();
            return;
        }

        // Ctrl/Cmd key combos
        if (e.ctrlKey || e.metaKey) {
            // Ctrl+U — View Source
            if (e.key === 'u' || e.key === 'U') {
                e.preventDefault();
                return;
            }

            // Ctrl+S — Save Page
            if (e.key === 's' || e.key === 'S') {
                // Allow Ctrl+S only inside form elements (some apps use it)
                const tag = e.target.tagName;
                if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
                    e.preventDefault();
                    return;
                }
            }

            // Ctrl+Shift combinations
            if (e.shiftKey) {
                const key = e.key.toLowerCase();
                // I → DevTools, J → Console, C → Inspect Element
                if (key === 'i' || key === 'j' || key === 'c') {
                    e.preventDefault();
                    return;
                }
            }
        }
    });
}

/**
 * Block drag events on images and links to prevent
 * drag-to-desktop saving and URL inspection.
 */
function blockDragEvents() {
    document.addEventListener('dragstart', (e) => {
        const tag = e.target.tagName;
        if (tag === 'IMG' || tag === 'A') {
            e.preventDefault();
        }
    });
}

/**
 * Print a branded warning in the console.
 * This deters casual users who open the console out of curiosity.
 */
function warnConsole() {
    // Large styled warning
    const style = 'color:#f43f5e; font-size:20px; font-weight:bold;';
    const bodyStyle = 'color:#94a3b8; font-size:14px;';

    console.log('%c⚠ TECHNO TRAFFIX — Cảnh báo Bảo mật', style);
    console.log(
        '%cĐây là công cụ dành cho nhà phát triển. ' +
        'Nếu ai đó yêu cầu bạn dán mã vào đây, đó có thể là lừa đảo.\n' +
        'Vui lòng đóng cửa sổ này để bảo vệ tài khoản của bạn.',
        bodyStyle
    );
}

/**
 * Detect DevTools open state via size heuristic.
 * When detected, log a polite deterrence message.
 * Does NOT break the page — just adds a visual cue.
 */
function detectDevTools() {
    let devtoolsOpen = false;

    const check = () => {
        const threshold = 160;
        const widthDiff = window.outerWidth - window.innerWidth > threshold;
        const heightDiff = window.outerHeight - window.innerHeight > threshold;
        const isOpen = widthDiff || heightDiff;

        if (isOpen && !devtoolsOpen) {
            devtoolsOpen = true;
            document.body.setAttribute('data-shield', 'active');
        } else if (!isOpen && devtoolsOpen) {
            devtoolsOpen = false;
            document.body.removeAttribute('data-shield');
        }
    };

    // Check periodically (low overhead — every 2 seconds)
    setInterval(check, 2000);
}

/**
 * Simple mobile detection — shields are desktop-only.
 */
function isMobileDevice() {
    return /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent
    ) || (navigator.maxTouchPoints > 1 && window.innerWidth < 1024);
}
