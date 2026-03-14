/**
 * Authentication Module - Sign In/Sign Out Component
 * Manages login state and modal interactions with enhanced registration
 */

class AuthManager {
    constructor() {
        this.isLoggedIn = false;
        this.currentUser = null;
        this.isRegisterMode = false;
        this.modal = null;
        this.authBtn = null;
        this.authBtnText = null;
        this.originalModalContent = null;
        this._trapFocusHandler = null;
        this._previouslyFocused = null;

        // Initialize
        this.init();
    }

    init() {
        // Get DOM elements
        this.modal = document.getElementById('auth-modal');
        this.authBtn = document.getElementById('auth-btn');
        this.authBtnText = document.getElementById('auth-btn-text');

        if (!this.modal || !this.authBtn) {
            console.warn('Auth elements not found');
            return;
        }

        // Save original content for restoration
        this.originalModalContent = this.modal.querySelector('.auth-modal__content').innerHTML;

        // Check for saved session
        this.checkSavedSession();

        // Bind events
        this.bindEvents();

        console.log('✅ AuthManager initialized');
    }

    bindEvents() {
        // Auth button click
        this.authBtn.addEventListener('click', () => this.handleAuthButtonClick());

        // Modal close button
        const closeBtn = document.getElementById('auth-modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeModal());
        }

        // Cancel button
        const cancelBtn = document.getElementById('auth-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.closeModal());
        }

        // Form submit
        const form = document.getElementById('auth-form');
        if (form) {
            form.addEventListener('submit', (e) => this.handleSubmit(e));
        }

        // Password toggle
        const togglePassword = document.getElementById('toggle-password');
        if (togglePassword) {
            togglePassword.addEventListener('click', () => this.togglePasswordVisibility());
        }

        // Password strength checker (register mode only)
        const passwordInput = document.getElementById('auth-password');
        if (passwordInput) {
            passwordInput.addEventListener('input', (e) => this.checkPasswordStrength(e.target.value));
        }

        // Close on overlay click
        const overlay = this.modal.querySelector('.auth-modal__overlay');
        if (overlay) {
            overlay.addEventListener('click', () => this.closeModal());
        }

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('auth-modal--open')) {
                this.closeModal();
            }
        });
    }

    checkSavedSession() {
        // Check localStorage for saved session
        const savedUser = localStorage.getItem('techno_traffix_user');
        const savedSession = localStorage.getItem('techno_traffix_session');

        if (savedUser && savedSession) {
            try {
                const user = JSON.parse(savedUser);
                if (savedSession === 'active') {
                    this.login(user, false);
                }
            } catch (e) {
                console.warn('Failed to parse saved session');
                this.clearSavedSession();
            }
        }
    }

    saveSession(user, remember = false) {
        if (remember) {
            localStorage.setItem('techno_traffix_user', JSON.stringify(user));
            localStorage.setItem('techno_traffix_session', 'active');
        } else {
            sessionStorage.setItem('techno_traffix_user', JSON.stringify(user));
            sessionStorage.setItem('techno_traffix_session', 'active');
        }
    }

    clearSavedSession() {
        localStorage.removeItem('techno_traffix_user');
        localStorage.removeItem('techno_traffix_session');
        sessionStorage.removeItem('techno_traffix_user');
        sessionStorage.removeItem('techno_traffix_session');
    }

    handleAuthButtonClick() {
        if (this.isLoggedIn) {
            this.showLogoutModal();
        } else {
            this.openModal();
        }
    }

    openModal(isRegister = false) {
        this.isRegisterMode = isRegister;
        this.updateModalContent();
        this.modal.classList.add('auth-modal--open');
        document.body.style.overflow = 'hidden';

        // Save currently focused element and set up focus trap
        this._previouslyFocused = document.activeElement;
        this._setupFocusTrap();

        // Focus on first visible input
        setTimeout(() => {
            const firstInput = this.isRegisterMode
                ? document.getElementById('auth-fullname')
                : document.getElementById('auth-username');
            if (firstInput) firstInput.focus();
        }, 100);
    }

    /** Trap Tab/Shift+Tab within the modal content. */
    _setupFocusTrap() {
        this._removeFocusTrap();
        const content = this.modal.querySelector('.auth-modal__content');
        if (!content) return;

        this._trapFocusHandler = (e) => {
            if (e.key !== 'Tab') return;
            const focusable = content.querySelectorAll(
                'input:not([disabled]):not([style*="display: none"]):not([tabindex="-1"]), ' +
                'button:not([disabled]):not([style*="display: none"]), ' +
                'a[href]:not([tabindex="-1"]), ' +
                '[tabindex]:not([tabindex="-1"]):not([disabled])'
            );
            const visible = [...focusable].filter(el => {
                const field = el.closest('.auth-modal__field--register');
                return !field || field.style.display !== 'none';
            });
            if (visible.length === 0) return;
            const first = visible[0];
            const last = visible[visible.length - 1];
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
        document.addEventListener('keydown', this._trapFocusHandler);
    }

    _removeFocusTrap() {
        if (this._trapFocusHandler) {
            document.removeEventListener('keydown', this._trapFocusHandler);
            this._trapFocusHandler = null;
        }
    }

    closeModal() {
        this.modal.classList.remove('auth-modal--open');
        document.body.style.overflow = '';
        this._removeFocusTrap();
        this.resetForm();

        // Restore focus to previously focused element
        if (this._previouslyFocused && this._previouslyFocused.focus) {
            this._previouslyFocused.focus();
            this._previouslyFocused = null;
        }

        // Reset to login mode after closing
        setTimeout(() => {
            this.isRegisterMode = false;
        }, 300);
    }

    toggleMode() {
        this.isRegisterMode = !this.isRegisterMode;
        this.updateModalContent();
        this.resetForm();

        // Focus on first field of new mode
        setTimeout(() => {
            const firstInput = this.isRegisterMode
                ? document.getElementById('auth-fullname')
                : document.getElementById('auth-username');
            if (firstInput) firstInput.focus();
        }, 100);
    }

    updateModalContent() {
        const title = this.modal.querySelector('.auth-modal__title');
        const subtitle = this.modal.querySelector('.auth-modal__subtitle');
        const submitBtn = document.getElementById('auth-submit');
        const submitText = submitBtn?.querySelector('.auth-modal__btn-text');
        const footer = document.getElementById('auth-footer');

        // Get all register-only fields
        const registerFields = document.querySelectorAll('.auth-modal__field--register');
        const rememberField = document.getElementById('remember-field');

        if (this.isRegisterMode) {
            // Registration mode
            title.textContent = 'Tạo tài khoản mới';
            subtitle.textContent = 'Điền đầy đủ thông tin để đăng ký tài khoản Techno Traffix';
            if (submitText) submitText.textContent = 'Đăng ký';

            // Show register fields
            registerFields.forEach(field => {
                field.style.display = 'block';
            });

            // Hide remember field
            if (rememberField) rememberField.style.display = 'none';

            // Update footer
            if (footer) {
                footer.querySelector('p').innerHTML = 'Đã có tài khoản? <a href="#" class="auth-modal__link" id="auth-switch">Đăng nhập ngay</a>';
            }
        } else {
            // Login mode
            title.textContent = 'Đăng nhập';
            subtitle.textContent = 'Đăng nhập để truy cập đầy đủ tính năng của Techno Traffix';
            if (submitText) submitText.textContent = 'Đăng nhập';

            // Hide register fields
            registerFields.forEach(field => {
                field.style.display = 'none';
            });

            // Show remember field
            if (rememberField) rememberField.style.display = 'block';

            // Update footer
            if (footer) {
                footer.querySelector('p').innerHTML = 'Chưa có tài khoản? <a href="#" class="auth-modal__link" id="auth-switch">Đăng ký ngay</a>';
            }
        }

        // Re-bind switch link event
        const switchLink = document.getElementById('auth-switch');
        if (switchLink) {
            switchLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleMode();
            });
        }

        // Re-bind terms link
        const termsLink = document.getElementById('terms-link');
        if (termsLink) {
            termsLink.addEventListener('click', (e) => {
                e.preventDefault();
                alert('Điều khoản sử dụng:\n\n1. Người dùng phải cung cấp thông tin chính xác\n2. Không sử dụng tài khoản cho mục đích bất hợp pháp\n3. Tuân thủ các quy định về bảo mật\n4. Chấp nhận các điều khoản dịch vụ của hệ thống');
            });
        }
    }

    checkPasswordStrength(password) {
        if (!this.isRegisterMode) return;

        const strengthFill = document.getElementById('strength-fill');
        const strengthText = document.getElementById('strength-text');

        if (!strengthFill || !strengthText) return;

        let strength = 0;
        let message = '';
        let className = '';

        if (password.length >= 8) strength++;
        if (password.length >= 12) strength++;
        if (/[A-Z]/.test(password)) strength++;
        if (/[0-9]/.test(password)) strength++;
        if (/[^A-Za-z0-9]/.test(password)) strength++;

        switch (strength) {
            case 0:
            case 1:
                message = 'Mật khẩu yếu - Cần ít nhất 8 ký tự';
                className = 'auth-modal__strength-fill--weak';
                break;
            case 2:
                message = 'Mật khẩu trung bình';
                className = 'auth-modal__strength-fill--fair';
                break;
            case 3:
            case 4:
                message = 'Mật khẩu khá mạnh';
                className = 'auth-modal__strength-fill--good';
                break;
            case 5:
                message = 'Mật khẩu rất mạnh';
                className = 'auth-modal__strength-fill--strong';
                break;
        }

        strengthFill.className = 'auth-modal__strength-fill ' + className;
        strengthText.textContent = message;
    }

    async handleSubmit(e) {
        e.preventDefault();

        const username = document.getElementById('auth-username').value.trim();
        const password = document.getElementById('auth-password').value;
        const errorDiv = document.getElementById('auth-error');

        // Reset error
        errorDiv.classList.remove('auth-modal__error--visible');
        errorDiv.textContent = '';

        if (this.isRegisterMode) {
            // Registration validation
            const fullname = document.getElementById('auth-fullname').value.trim();
            const phone = document.getElementById('auth-phone').value.trim();
            const email = document.getElementById('auth-email').value.trim();
            const confirmPassword = document.getElementById('auth-confirm-password').value;
            const termsAccepted = document.getElementById('auth-terms').checked;

            // Validate full name
            if (!fullname) {
                this.showError('Vui lòng nhập họ và tên');
                return;
            }
            if (fullname.length < 2) {
                this.showError('Họ và tên phải có ít nhất 2 ký tự');
                return;
            }

            // Validate phone
            if (!phone) {
                this.showError('Vui lòng nhập số điện thoại');
                return;
            }
            const phoneRegex = /^[0-9]{10,11}$/;
            if (!phoneRegex.test(phone.replace(/\s/g, ''))) {
                this.showError('Số điện thoại không hợp lệ (cần 10-11 số)');
                return;
            }

            // Validate email
            if (!email) {
                this.showError('Vui lòng nhập địa chỉ email');
                return;
            }
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                this.showError('Địa chỉ email không hợp lệ');
                return;
            }

            // Validate username
            if (!username) {
                this.showError('Vui lòng nhập tên đăng nhập');
                return;
            }
            if (username.length < 3) {
                this.showError('Tên đăng nhập phải có ít nhất 3 ký tự');
                return;
            }
            if (!/^[a-zA-Z0-9_]+$/.test(username)) {
                this.showError('Tên đăng nhập chỉ được chứa chữ cái, số và dấu gạch dưới');
                return;
            }

            // Validate password
            if (!password) {
                this.showError('Vui lòng nhập mật khẩu');
                return;
            }
            if (password.length < 8) {
                this.showError('Mật khẩu phải có ít nhất 8 ký tự');
                return;
            }

            // Validate confirm password
            if (password !== confirmPassword) {
                this.showError('Mật khẩu xác nhận không khớp');
                return;
            }

            // Validate terms
            if (!termsAccepted) {
                this.showError('Vui lòng đồng ý với điều khoản sử dụng');
                return;
            }

            // Show loading
            this.setLoading(true);

            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 1500));

            // Check if username exists
            const existingUsers = JSON.parse(localStorage.getItem('techno_traffix_users') || '[]');
            if (existingUsers.find(u => u.username === username)) {
                this.showError('Tên đăng nhập đã tồn tại');
                this.setLoading(false);
                return;
            }

            // Check if email exists
            if (existingUsers.find(u => u.email === email)) {
                this.showError('Email này đã được sử dụng');
                this.setLoading(false);
                return;
            }

            // Create new user
            const newUser = {
                username,
                fullname,
                phone,
                email,
                created: Date.now(),
                id: Date.now()
            };

            existingUsers.push(newUser);
            localStorage.setItem('techno_traffix_users', JSON.stringify(existingUsers));

            // Auto login after registration
            this.login(newUser, true);
            this.showSuccess('Đăng ký thành công!');

        } else {
            // Login validation
            if (!username || !password) {
                this.showError('Vui lòng nhập đầy đủ thông tin');
                return;
            }

            const remember = document.getElementById('auth-remember')?.checked || false;

            // Show loading
            this.setLoading(true);

            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 1500));

            // Check if user exists
            const existingUsers = JSON.parse(localStorage.getItem('techno_traffix_users') || '[]');
            const user = existingUsers.find(u => u.username === username);

            if (!user) {
                // Auto-create user for demo purposes
                const newUser = {
                    username,
                    fullname: username,
                    phone: '',
                    email: `${username}@example.com`,
                    created: Date.now(),
                    id: Date.now()
                };
                existingUsers.push(newUser);
                localStorage.setItem('techno_traffix_users', JSON.stringify(existingUsers));
                this.login(newUser, remember);
            } else {
                this.login(user, remember);
            }

            this.showSuccess('Đăng nhập thành công!');
        }

        this.setLoading(false);
    }

    login(user, remember = false) {
        this.isLoggedIn = true;
        this.currentUser = user;

        // Save session
        this.saveSession(user, remember);

        // Update UI
        this.updateAuthButton();

        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('auth:login', {
            detail: { user: this.currentUser }
        }));
    }

    logout() {
        this.isLoggedIn = false;
        this.currentUser = null;

        // Clear session
        this.clearSavedSession();

        // Update UI
        this.updateAuthButton();

        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('auth:logout'));

        console.log('👋 User logged out');
    }

    showLogoutModal() {
        const content = this.modal.querySelector('.auth-modal__content');

        content.innerHTML = `
            <div class="auth-modal__header">
                <div class="auth-modal__logo">
                    <svg width="32" height="32" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                            d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                </div>
                <h2 class="auth-modal__title">Đăng xuất</h2>
                <p class="auth-modal__subtitle">Bạn có chắc chắn muốn đăng xuất?</p>
                <button class="auth-modal__close" id="auth-modal-close" aria-label="Đóng">
                    <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
            
            <div class="auth-modal__user-info">
                <div class="auth-modal__avatar">
                    ${this.currentUser.fullname ? this.currentUser.fullname.charAt(0).toUpperCase() : this.currentUser.username.charAt(0).toUpperCase()}
                </div>
                <div class="auth-modal__user-details">
                    <h3>${this.currentUser.fullname || this.currentUser.username}</h3>
                    <p>${this.currentUser.email || ''}</p>
                </div>
            </div>
            
            <div class="auth-modal__form">
                <div class="auth-modal__actions">
                    <button type="button" class="auth-modal__btn auth-modal__btn--secondary" id="auth-cancel-logout">
                        Hủy bỏ
                    </button>
                    <button type="button" class="auth-modal__btn auth-modal__btn--danger" id="auth-confirm-logout">
                        <span>Đăng xuất</span>
                    </button>
                </div>
            </div>
        `;

        this.modal.classList.add('auth-modal--open');
        document.body.style.overflow = 'hidden';

        document.getElementById('auth-modal-close').addEventListener('click', () => {
            this.closeLogoutModal();
        });

        document.getElementById('auth-cancel-logout').addEventListener('click', () => {
            this.closeLogoutModal();
        });

        document.getElementById('auth-confirm-logout').addEventListener('click', () => {
            this.logout();
            this.closeLogoutModal();
        });

        const overlay = this.modal.querySelector('.auth-modal__overlay');
        if (overlay) {
            overlay.addEventListener('click', () => this.closeLogoutModal());
        }
    }

    closeLogoutModal() {
        this.modal.classList.remove('auth-modal--open');
        document.body.style.overflow = '';

        if (this.originalModalContent) {
            setTimeout(() => {
                const content = this.modal.querySelector('.auth-modal__content');
                content.innerHTML = this.originalModalContent;
                this.bindEvents();
                this.isRegisterMode = false;
                this.updateModalContent();
            }, 300);
        }
    }

    updateAuthButton() {
        const avatar = document.getElementById('auth-btn-avatar');

        if (this.isLoggedIn) {
            this.authBtnText.textContent = 'Đăng xuất';
            this.authBtn.classList.add('auth-btn--logged-in');
            const displayName = this.currentUser.fullname || this.currentUser.username;
            this.authBtn.title = `Đăng xuất (${displayName})`;

            if (avatar) {
                avatar.textContent = displayName.charAt(0).toUpperCase();
            }
        } else {
            this.authBtnText.textContent = 'Đăng nhập';
            this.authBtn.classList.remove('auth-btn--logged-in');
            this.authBtn.title = 'Đăng nhập';

            if (avatar) {
                avatar.textContent = '';
            }
        }
    }

    showError(message) {
        const errorDiv = document.getElementById('auth-error');
        errorDiv.textContent = message;
        errorDiv.classList.add('auth-modal__error--visible');

        const form = document.getElementById('auth-form');
        form.style.animation = 'shake 0.5s ease';
        setTimeout(() => {
            form.style.animation = '';
        }, 500);
    }

    showSuccess(message) {
        const content = this.modal.querySelector('.auth-modal__content');
        const displayName = this.currentUser.fullname || this.currentUser.username;

        content.innerHTML = `
            <div class="auth-modal__success">
                <div class="auth-modal__success-icon">
                    <svg width="40" height="40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                    </svg>
                </div>
                <h3 class="auth-modal__success-title">${message}</h3>
                <p class="auth-modal__success-text">Chào mừng, ${displayName}!</p>
            </div>
        `;

        setTimeout(() => {
            this.closeModal();
            setTimeout(() => {
                if (this.originalModalContent) {
                    content.innerHTML = this.originalModalContent;
                    this.bindEvents();
                    this.isRegisterMode = false;
                    this.updateModalContent();
                }
            }, 300);
        }, 1500);
    }

    setLoading(isLoading) {
        const submitBtn = document.getElementById('auth-submit');
        const submitText = submitBtn.querySelector('.auth-modal__btn-text');
        const spinner = submitBtn.querySelector('.auth-modal__spinner');

        submitBtn.disabled = isLoading;

        if (isLoading) {
            submitText.classList.add('hidden');
            spinner.classList.remove('hidden');
        } else {
            submitText.classList.remove('hidden');
            spinner.classList.add('hidden');
        }
    }

    togglePasswordVisibility() {
        const passwordInput = document.getElementById('auth-password');
        const eyeIcon = document.querySelector('.auth-modal__eye');
        const eyeOffIcon = document.querySelector('.auth-modal__eye-off');

        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            eyeIcon.classList.add('hidden');
            eyeOffIcon.classList.remove('hidden');
        } else {
            passwordInput.type = 'password';
            eyeIcon.classList.remove('hidden');
            eyeOffIcon.classList.add('hidden');
        }
    }

    resetForm() {
        const form = document.getElementById('auth-form');
        if (form) {
            form.reset();
        }

        const errorDiv = document.getElementById('auth-error');
        if (errorDiv) {
            errorDiv.classList.remove('auth-modal__error--visible');
            errorDiv.textContent = '';
        }

        // Reset password visibility
        const passwordInput = document.getElementById('auth-password');
        if (passwordInput) {
            passwordInput.type = 'password';
        }

        const eyeIcon = document.querySelector('.auth-modal__eye');
        const eyeOffIcon = document.querySelector('.auth-modal__eye-off');
        if (eyeIcon && eyeOffIcon) {
            eyeIcon.classList.remove('hidden');
            eyeOffIcon.classList.add('hidden');
        }

        // Reset password strength
        if (this.isRegisterMode) {
            this.checkPasswordStrength('');
        }
    }

    // Public API methods
    isAuthenticated() {
        return this.isLoggedIn;
    }

    getCurrentUser() {
        return this.currentUser;
    }
}

// Initialize and export
let authManager = null;

export function initAuth() {
    authManager = new AuthManager();
    return authManager;
}

export function getAuthManager() {
    return authManager;
}

export default AuthManager;
