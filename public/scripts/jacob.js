let textVisuals = [];
let currentVisualIndex = -1;

// Suppress console warnings from iframe content (Tailwind CSS warnings, etc.)
const originalWarn = console.warn;
console.warn = function(...args) {
    const message = args.join(' ');
    if (message.includes('cdn.tailwindcss.com') || message.includes('Tailwind CSS')) {
        return;
    }
    originalWarn.apply(console, args);
};

// Suppress MutationObserver errors from browser extensions observing iframes
const originalError = console.error;
console.error = function(...args) {
    const message = args.join(' ');
    if (message.includes('web-client-content-script') ||
        (message.includes('MutationObserver') && message.includes('observe')) ||
        (message.includes('Failed to execute') && message.includes('observe') && message.includes('MutationObserver'))) {
        return;
    }
    originalError.apply(console, args);
};

window.addEventListener('load', () => {
    setupButtonListeners();
    loadTextVisuals();
});

async function loadTextVisuals() {
    try {
        const response = await fetch('scripts/jacob_text_visuals.json');
        textVisuals = await response.json();
        populateNavigation();
        if (textVisuals.length > 0) {
            selectVisual(0);
        }
    } catch (error) {
        console.error('Error loading text visuals:', error);
        alert('Error loading text visuals: ' + error.message);
    }
}

function populateNavigation() {
    const navList = document.getElementById('nav-list');
    navList.innerHTML = '';
    textVisuals.forEach((visual, index) => {
        if (visual.major_heading) {
            const header = document.createElement('div');
            header.className = 'nav-major-header';
            header.textContent = visual.major_heading;
            navList.appendChild(header);
        }
        if (visual.minor_heading) {
            const header = document.createElement('div');
            header.className = 'nav-minor-header';
            header.textContent = visual.minor_heading;
            navList.appendChild(header);
        }
        const navItem = document.createElement('div');
        navItem.className = 'nav-item';
        navItem.textContent = visual.verse_range;
        navItem.dataset.index = index;
        navItem.addEventListener('click', () => selectVisual(index));
        navList.appendChild(navItem);
    });
}

function selectVisual(index) {
    if (index < 0 || index >= textVisuals.length) return;

    currentVisualIndex = index;
    const visual = textVisuals[index];

    document.querySelectorAll('.nav-item').forEach((item, i) => {
        item.classList.toggle('selected', i === index);
    });

    document.getElementById('bible-visual-iframe').src = visual.url;
    updateNavButtons();
}

function updateNavButtons() {
    document.getElementById('prev-btn').disabled = currentVisualIndex <= 0;
    document.getElementById('next-btn').disabled = currentVisualIndex >= textVisuals.length - 1;
}

function setupButtonListeners() {
    document.getElementById('prev-btn').addEventListener('click', () => {
        if (currentVisualIndex > 0) selectVisual(currentVisualIndex - 1);
    });
    document.getElementById('next-btn').addEventListener('click', () => {
        if (currentVisualIndex < textVisuals.length - 1) selectVisual(currentVisualIndex + 1);
    });
    setupMobileMenu();
}

function setupMobileMenu() {
    const hamburgerBtn = document.getElementById('hamburger-btn');
    const navColumn = document.getElementById('nav-column');
    const navCloseBtn = document.getElementById('nav-close-btn');
    let navOpen = false;

    function isMobile() {
        return window.innerWidth <= 600;
    }

    function updateVisibility() {
        if (isMobile()) {
            hamburgerBtn.style.display = 'block';
            navCloseBtn.style.display = 'block';
            if (!navOpen) navColumn.style.display = 'none';
        } else {
            hamburgerBtn.style.display = 'none';
            navCloseBtn.style.display = 'none';
            navColumn.style.display = '';
            navOpen = false;
        }
    }

    function closeNav() {
        navOpen = false;
        if (isMobile()) navColumn.style.display = 'none';
    }

    hamburgerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        navOpen = !navOpen;
        navColumn.style.display = navOpen ? 'flex' : 'none';
        if (navOpen) navColumn.classList.add('mobile-visible');
        else navColumn.classList.remove('mobile-visible');
    });

    navCloseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeNav();
    });

    document.addEventListener('click', (e) => {
        if (isMobile() && navOpen && !navColumn.contains(e.target) && e.target !== hamburgerBtn) {
            closeNav();
        }
    });

    navColumn.addEventListener('click', (e) => e.stopPropagation());

    window.addEventListener('resize', () => {
        updateVisibility();
    });

    updateVisibility();
}
