/**
 * Theme Module - Light/Dark mode switching
 * Handles toggle, persistence, system preference detection, and meta tag updates
 */

const STORAGE_KEY = 'techno-traffix-theme';
const DARK = 'dark';
const LIGHT = 'light';

/**
 * Get the user's preferred theme:
 * 1. Check localStorage for saved preference
 * 2. Fall back to system preference (prefers-color-scheme)
 * 3. Default to dark
 */
function getPreferredTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === DARK || saved === LIGHT) return saved;

    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        return LIGHT;
    }
    return DARK;
}

/**
 * Apply theme to the document
 */
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);

    // Update meta theme-color
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
        meta.setAttribute('content', theme === LIGHT ? '#f0f2f5' : '#060a13');
    }

    // Update toggle button aria-label
    const btn = document.getElementById('theme-toggle');
    if (btn) {
        btn.setAttribute(
            'aria-label',
            theme === LIGHT ? 'Chuyển sang giao diện tối' : 'Chuyển sang giao diện sáng'
        );
    }
}

/**
 * Initialize theme system
 */
export function initTheme() {
    // Apply saved/system theme immediately (prevents FOUC)
    const initialTheme = getPreferredTheme();
    applyTheme(initialTheme);

    // Wait for DOM ready to attach toggle listener
    const btn = document.getElementById('theme-toggle');
    if (btn) {
        btn.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme') || DARK;
            const next = current === DARK ? LIGHT : DARK;
            applyTheme(next);
            localStorage.setItem(STORAGE_KEY, next);
        });
    }

    // Listen for system preference changes (while no user preference saved)
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
            // Only react if user hasn't explicitly chosen
            if (!localStorage.getItem(STORAGE_KEY)) {
                applyTheme(e.matches ? LIGHT : DARK);
            }
        });
    }

    console.log(`🎨 Theme initialized: ${initialTheme}`);
}
