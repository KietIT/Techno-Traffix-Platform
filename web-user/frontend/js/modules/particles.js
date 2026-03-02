/**
 * Particle System - Mouse Gravity Repulsion Effect
 * Lightweight canvas-based physics simulation (full viewport, all tabs)
 */

// Module-level animation state so pauseParticles/resumeParticles can access it
let animationId = null;
let loopFn = null;

export function initParticles() {
    const canvas = document.getElementById('hero-particles');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Config
    const REPULSION_RADIUS = 120;
    const REPULSION_RADIUS_SQ = REPULSION_RADIUS * REPULSION_RADIUS;
    const REPULSION_STRENGTH = 800;
    const FRICTION = 0.98;
    const BASE_SPEED = 0.4;
    const MIN_RADIUS = 2;
    const MAX_RADIUS = 4;

    let particles = [];
    let mouse = { x: -9999, y: -9999 };

    function getParticleCount() {
        return window.innerWidth < 768 ? 25 : 50;
    }

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    function createParticles() {
        const count = getParticleCount();
        particles = [];
        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * BASE_SPEED * 2,
                vy: (Math.random() - 0.5) * BASE_SPEED * 2,
                radius: MIN_RADIUS + Math.random() * (MAX_RADIUS - MIN_RADIUS),
                opacity: 0.15 + Math.random() * 0.35
            });
        }
    }

    function update() {
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];

            // Mouse repulsion
            const dx = p.x - mouse.x;
            const dy = p.y - mouse.y;
            const distSq = dx * dx + dy * dy;

            if (distSq < REPULSION_RADIUS_SQ && distSq > 0) {
                const dist = Math.sqrt(distSq);
                const force = REPULSION_STRENGTH / (distSq + 1);
                p.vx += (dx / dist) * force;
                p.vy += (dy / dist) * force;
            }

            // Apply friction
            p.vx *= FRICTION;
            p.vy *= FRICTION;

            // Drift: nudge back toward base speed if nearly still
            if (Math.abs(p.vx) < 0.1 && Math.abs(p.vy) < 0.1) {
                p.vx += (Math.random() - 0.5) * BASE_SPEED * 0.5;
                p.vy += (Math.random() - 0.5) * BASE_SPEED * 0.5;
            }

            // Move
            p.x += p.vx;
            p.y += p.vy;

            // Edge bouncing
            if (p.x < p.radius) {
                p.x = p.radius;
                p.vx *= -1;
            } else if (p.x > canvas.width - p.radius) {
                p.x = canvas.width - p.radius;
                p.vx *= -1;
            }

            if (p.y < p.radius) {
                p.y = p.radius;
                p.vy *= -1;
            } else if (p.y > canvas.height - p.radius) {
                p.y = canvas.height - p.radius;
                p.vy *= -1;
            }
        }
    }

    function getParticleColor(opacity) {
        const theme = document.documentElement.getAttribute('data-theme');
        if (theme === 'light') {
            return `rgba(8, 145, 178, ${opacity * 0.6})`;
        }
        return `rgba(59, 130, 246, ${opacity})`;
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fillStyle = getParticleColor(p.opacity);
            ctx.fill();
        }
    }

    function loop() {
        update();
        draw();
        animationId = requestAnimationFrame(loop);
    }

    // Mouse tracking (viewport coordinates = canvas coordinates for fixed canvas)
    document.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    document.addEventListener('mouseleave', () => {
        mouse.x = -9999;
        mouse.y = -9999;
    });

    // Touch support
    document.addEventListener('touchmove', (e) => {
        if (e.touches.length > 0) {
            mouse.x = e.touches[0].clientX;
            mouse.y = e.touches[0].clientY;
        }
    }, { passive: true });

    document.addEventListener('touchend', () => {
        mouse.x = -9999;
        mouse.y = -9999;
    });

    // Pause when tab not visible
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            if (animationId) {
                cancelAnimationFrame(animationId);
                animationId = null;
            }
        } else {
            if (!animationId) loop();
        }
    });

    // Resize handling (debounced to avoid thrashing on rapid resize events)
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            resize();
            const targetCount = getParticleCount();
            if (particles.length !== targetCount) {
                createParticles();
            }
        }, 150);
    });

    // Init
    resize();
    createParticles();
    loopFn = loop;
    loop();
}

/** Pause the particle animation loop (e.g. when switching away from overview tab). */
export function pauseParticles() {
    if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
    }
}

/** Resume the particle animation loop. */
export function resumeParticles() {
    if (!animationId && loopFn) {
        loopFn();
    }
}
