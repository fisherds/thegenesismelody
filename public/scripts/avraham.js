// Global state
let textVisuals = [];
let currentVisualIndex = -1;
let selectedVerses = new Set(); // Store as "chapter:verse" strings

// Voting feature state (only used on avraham-dense.html)
let resultRatings = {}; // Store ratings for each result by index: { 0: "5", 1: "", ... }
let currentResults = []; // Store current search results
let feedbackSubmitted = false; // Track if feedback has been submitted for current search
let isSubmitting = false; // Prevent double submission

// Firestore instance (initialized on window load)
let db = null;
let submitButtonHandler = null; // Store reference to submit handler for removal

// Helper function to detect if we're on avraham-dense.html (has search interface)
// avraham.html doesn't have a real search interface, so we check for the actual search controls section
function isDensePage() {
    const searchControls = document.querySelector('section[name="search_controls"]');
    if (!searchControls) return false;
    // Check if it's actually visible (not a dummy element)
    const computedStyle = window.getComputedStyle(searchControls);
    return computedStyle.display !== 'none' && searchControls.offsetParent !== null;
}

// Suppress console warnings from iframe content (Tailwind CSS warnings, etc.)
const originalWarn = console.warn;
console.warn = function(...args) {
    const message = args.join(' ');
    // Filter out Tailwind CDN warnings from iframe content
    if (message.includes('cdn.tailwindcss.com') || message.includes('Tailwind CSS')) {
        return; // Suppress this warning
    }
    originalWarn.apply(console, args);
};

// Suppress console errors from browser extensions trying to observe iframes
const originalError = console.error;
console.error = function(...args) {
    const message = args.join(' ');
    // Filter out MutationObserver errors from browser extensions
    if (message.includes('web-client-content-script') || 
        (message.includes('MutationObserver') && message.includes('observe')) ||
        (message.includes('Failed to execute') && message.includes('observe') && message.includes('MutationObserver'))) {
        return; // Suppress this error
    }
    originalError.apply(console, args);
};

window.addEventListener("load", (event) => {
    console.log("page is fully loaded");
    
    // Initialize Firestore if Firebase is available
    if (typeof firebase !== 'undefined' && firebase.firestore) {
        db = firebase.firestore();
        console.log("Firestore initialized");
    } else {
        console.warn("Firebase/Firestore not available - feedback saving will be disabled");
    }
    
    setupButtonListeners();
    loadTextVisuals();
    setupResizer();
    setupPanelToggles();
    setupAudioPlayer();
});

async function loadTextVisuals() {
    try {
        const response = await fetch('scripts/text_visuals.json');
        textVisuals = await response.json();
        console.log(`Loaded ${textVisuals.length} text visuals`);
        populateNavigation();
        // Select first item by default
        if (textVisuals.length > 0) {
            selectVisual(0);
        }
        // Initialize audio player after visuals are loaded
        if (audioPlayer) {
            updateAudioForCurrentVisual();
        }
    } catch (error) {
        console.error("Error loading text visuals:", error);
        alert("Error loading text visuals: " + error.message);
    }
}

function populateNavigation() {
    const navList = document.getElementById('nav-list');
    navList.innerHTML = '';
    
    let currentHeader = null;
    
    textVisuals.forEach((visual, index) => {
        // Add header if this visual has one and it's different from current
        if (visual.header && visual.header !== currentHeader) {
            const headerDiv = document.createElement('div');
            headerDiv.className = 'nav-section-header';
            headerDiv.textContent = visual.header;
            navList.appendChild(headerDiv);
            currentHeader = visual.header;
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
    
    // Update navigation selection
    document.querySelectorAll('.nav-item').forEach((item, i) => {
        if (i === index) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
    
    // Update iframe
    const iframe = document.getElementById('bible-visual-iframe');
    iframe.src = visual.url;
    
    // Populate verse selection column
    populateVerseSelection(visual.verses);
    
    // Update navigation buttons
    updateNavButtons();
    
    // Only update audio if it's not currently playing (don't interrupt playback)
    if (!audioPlayer || audioPlayer.paused) {
        updateAudioForCurrentVisual();
    }
}

function populateVerseSelection(verses) {
    const verseList = document.getElementById('verse-list');
    const selectAllBtn = document.getElementById('select-all-btn');
    verseList.innerHTML = '';
    
    if (verses.length === 0) {
        selectAllBtn.style.display = 'none';
        return;
    }
    
    // Show "All" button if there are verses
    selectAllBtn.style.display = 'block';
    
    verses.forEach(verse => {
        const verseKey = `${verse.chapter}:${verse.verse}`;
        const isSelected = selectedVerses.has(verseKey);
        
        const verseItem = document.createElement('div');
        verseItem.className = 'verse-checkbox-item' + (isSelected ? ' selected' : '');
        verseItem.dataset.chapter = verse.chapter;
        verseItem.dataset.verse = verse.verse;
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = isSelected;
        checkbox.addEventListener('change', (e) => {
            e.stopPropagation();
            toggleVerseSelection(verse.chapter, verse.verse, e.target.checked);
        });
        
        const verseText = document.createTextNode(`${verse.chapter}:${verse.verse}`);
        verseItem.appendChild(checkbox);
        verseItem.appendChild(verseText);
        
        verseItem.addEventListener('click', (e) => {
            if (e.target !== checkbox) {
                checkbox.checked = !checkbox.checked;
                toggleVerseSelection(verse.chapter, verse.verse, checkbox.checked);
            }
        });
        
        verseList.appendChild(verseItem);
    });
    
    // Update select all button state
    updateSelectAllButton();
}

function toggleVerseSelection(chapter, verse, isSelected) {
    const verseKey = `${chapter}:${verse}`;
    
    if (isSelected) {
        selectedVerses.add(verseKey);
    } else {
        selectedVerses.delete(verseKey);
    }
    
    // Update UI
    const verseItem = document.querySelector(`.verse-checkbox-item[data-chapter="${chapter}"][data-verse="${verse}"]`);
    if (verseItem) {
        if (isSelected) {
            verseItem.classList.add('selected');
        } else {
            verseItem.classList.remove('selected');
        }
    }
    
    // Update Search Verses field
    updateSearchVersesField();
    
    // Update "All" button state
    updateSelectAllButton();
}

function updateSearchVersesField() {
    const searchVersesField = document.getElementById('search_verses');
    const versesArray = Array.from(selectedVerses)
        .map(key => {
            const [chapter, verse] = key.split(':');
            return { chapter: parseInt(chapter), verse: parseInt(verse) };
        })
        .sort((a, b) => {
            if (a.chapter !== b.chapter) return a.chapter - b.chapter;
            return a.verse - b.verse;
        });
    
    searchVersesField.value = JSON.stringify(versesArray, null, 2);
    updateClearVersesButton();
    validateSearchButton(); // Also validate search button when verses change
}

function updateNavButtons() {
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    
    prevBtn.disabled = currentVisualIndex <= 0;
    nextBtn.disabled = currentVisualIndex >= textVisuals.length - 1;
}

function setupButtonListeners() {
    document.querySelector("#search_button").addEventListener("click", performSearch);
    document.getElementById("prev-btn").addEventListener("click", () => {
        if (currentVisualIndex > 0) {
            selectVisual(currentVisualIndex - 1);
        }
    });
    document.getElementById("next-btn").addEventListener("click", () => {
        if (currentVisualIndex < textVisuals.length - 1) {
            selectVisual(currentVisualIndex + 1);
        }
    });
    document.getElementById("clear-all-btn").addEventListener("click", clearAllVerses);
    
    // Add listeners for model and record_level changes to validate combinations
    document.getElementById("model_name").addEventListener("change", validateSearchButton);
    document.getElementById("record_level").addEventListener("change", validateSearchButton);
    
    // Add listener for Clear Verses button
    document.getElementById("clear_verses_button").addEventListener("click", clearSearchVerses);
    
    // Add listener for search_verses textarea changes to enable/disable Clear button and Search button
    document.getElementById("search_verses").addEventListener("input", () => {
        updateClearVersesButton();
        validateSearchButton();
    });
    
    // Add listener for "All" button
    document.getElementById("select-all-btn").addEventListener("click", selectAllVerses);
    
    // Add listener for Full Screen button
    document.getElementById("fullscreen-btn").addEventListener("click", toggleFullScreen);
    
    // Setup mobile functionality
    setupMobileMenu();
    
    // Initial validation
    validateSearchButton();
    updateClearVersesButton();
}

function selectAllVerses() {
    // Get all checkboxes in the current verse list
    const checkboxes = document.querySelectorAll('#verse-list .verse-checkbox-item input[type="checkbox"]');
    
    if (checkboxes.length === 0) return;
    
    // Check if all are already selected
    const allSelected = Array.from(checkboxes).every(cb => cb.checked);
    
    // Toggle all checkboxes
    checkboxes.forEach(checkbox => {
        const verseItem = checkbox.closest('.verse-checkbox-item');
        const chapter = parseInt(verseItem.dataset.chapter);
        const verse = parseInt(verseItem.dataset.verse);
        const shouldSelect = !allSelected;
        
        checkbox.checked = shouldSelect;
        toggleVerseSelection(chapter, verse, shouldSelect);
    });
    
    // Update button text
    updateSelectAllButton();
}

function updateSelectAllButton() {
    const checkboxes = document.querySelectorAll('#verse-list .verse-checkbox-item input[type="checkbox"]');
    const selectAllBtn = document.getElementById('select-all-btn');
    
    if (checkboxes.length === 0) {
        selectAllBtn.style.display = 'none';
        return;
    }
    
    const allSelected = Array.from(checkboxes).every(cb => cb.checked);
    selectAllBtn.textContent = allSelected ? 'Deselect All' : 'All';
}

function clearAllVerses() {
    selectedVerses.clear();
    // Update all checkboxes
    document.querySelectorAll('.verse-checkbox-item input[type="checkbox"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    document.querySelectorAll('.verse-checkbox-item').forEach(item => {
        item.classList.remove('selected');
    });
    updateSearchVersesField();
}

let savedLeftWidth = 70; // Default 70%

function setupResizer() {
    const resizer = document.getElementById('resizer');
    const leftPanel = document.getElementById('left-panel');
    const rightPanel = document.getElementById('right-panel');
    
    let isResizing = false;
    
    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });
    
    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        
        const containerWidth = document.querySelector('.main-container').offsetWidth;
        const newLeftWidth = (e.clientX / containerWidth) * 100;
        
        // Constrain between 20% and 80%
        const minLeftWidth = 20;
        const maxLeftWidth = 80;
        const constrainedWidth = Math.max(minLeftWidth, Math.min(maxLeftWidth, newLeftWidth));
        
        savedLeftWidth = constrainedWidth;
        leftPanel.style.width = `${constrainedWidth}%`;
        rightPanel.style.width = `${100 - constrainedWidth}%`;
    });
    
    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

function setupPanelToggles() {
    const leftToggle = document.getElementById('left-panel-toggle');
    const rightToggle = document.getElementById('right-panel-toggle');
    const leftPanel = document.getElementById('left-panel');
    const rightPanel = document.getElementById('right-panel');
    const resizer = document.getElementById('resizer');
    
    // Create restore buttons (initially hidden)
    const leftRestore = document.createElement('button');
    leftRestore.className = 'panel-restore left-restore';
    leftRestore.innerHTML = '☰';
    leftRestore.title = 'Show Bible Reader';
    leftRestore.style.display = 'none';
    document.body.appendChild(leftRestore);
    
    const rightRestore = document.createElement('button');
    rightRestore.className = 'panel-restore right-restore';
    rightRestore.innerHTML = '🔍';
    rightRestore.title = 'Show Search';
    rightRestore.style.display = 'none';
    document.body.appendChild(rightRestore);
    
    leftToggle.addEventListener('click', () => {
        // If right panel is already hidden, don't allow closing left panel
        if (rightPanel.style.display === 'none') {
            rightPanel.style.display = 'block';
            resizer.style.display = 'block';
            leftPanel.style.width = `${savedLeftWidth}%`;
            rightPanel.style.width = `${100 - savedLeftWidth}%`;
            rightRestore.style.display = 'none';
            return;
        }
        
        leftPanel.style.display = 'none';
        resizer.style.display = 'none';
        rightPanel.style.width = '100%';
        leftRestore.style.display = 'flex';
    });
    
    rightToggle.addEventListener('click', () => {
        // If left panel is already hidden, don't allow closing right panel
        if (leftPanel.style.display === 'none') {
            leftPanel.style.display = 'flex';
            resizer.style.display = 'block';
            leftPanel.style.width = `${savedLeftWidth}%`;
            rightPanel.style.width = `${100 - savedLeftWidth}%`;
            leftRestore.style.display = 'none';
            return;
        }
        
        rightPanel.style.display = 'none';
        resizer.style.display = 'none';
        leftPanel.style.width = '100%';
        rightRestore.style.display = 'flex';
    });
    
    leftRestore.addEventListener('click', () => {
        leftPanel.style.display = 'flex';
        resizer.style.display = 'block';
        leftPanel.style.width = `${savedLeftWidth}%`;
        rightPanel.style.width = `${100 - savedLeftWidth}%`;
        rightPanel.style.display = 'block';
        leftRestore.style.display = 'none';
    });
    
    rightRestore.addEventListener('click', () => {
        rightPanel.style.display = 'block';
        resizer.style.display = 'block';
        leftPanel.style.width = `${savedLeftWidth}%`;
        rightPanel.style.width = `${100 - savedLeftWidth}%`;
        rightRestore.style.display = 'none';
    });
}

function setupMobileMenu() {
    const hamburgerBtn = document.getElementById('hamburger-btn');
    const navColumn = document.getElementById('nav-column');
    const verseColumn = document.getElementById('verse-selection-column');
    const navCloseBtn = document.getElementById('nav-close-btn');
    const verseCloseBtn = document.getElementById('verse-close-btn');
    
    let currentOpenPanel = null;
    
    function isMobile() {
        return window.innerWidth <= 600;
    }
    
    function updateMobileVisibility() {
        if (isMobile()) {
            hamburgerBtn.style.display = 'block';
            navCloseBtn.style.display = 'block';
            verseCloseBtn.style.display = 'block';
            // Hide columns by default on mobile
            if (!navColumn.classList.contains('mobile-visible')) {
                navColumn.style.display = 'none';
            }
            if (!verseColumn.classList.contains('mobile-visible')) {
                verseColumn.style.display = 'none';
            }
        } else {
            hamburgerBtn.style.display = 'none';
            navCloseBtn.style.display = 'none';
            verseCloseBtn.style.display = 'none';
            navColumn.style.display = '';
            verseColumn.style.display = '';
            navColumn.classList.remove('mobile-visible');
            verseColumn.classList.remove('mobile-visible');
        }
    }
    
    function closeAllPanels() {
        navColumn.classList.remove('mobile-visible');
        verseColumn.classList.remove('mobile-visible');
        if (isMobile()) {
            navColumn.style.display = 'none';
            verseColumn.style.display = 'none';
        }
        currentOpenPanel = null;
    }
    
    function openPanel(panel) {
        closeAllPanels();
        if (isMobile()) {
            panel.classList.add('mobile-visible');
            panel.style.display = 'flex';
            currentOpenPanel = panel;
        }
    }
    
    function toggleNavPanel() {
        if (!isMobile()) return;
        
        if (currentOpenPanel === navColumn) {
            closeAllPanels();
        } else {
            openPanel(navColumn);
        }
    }
    
    hamburgerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleNavPanel();
    });
    
    navCloseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeAllPanels();
    });
    
    verseCloseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeAllPanels();
    });
    
    // Close panels when clicking outside
    document.addEventListener('click', (e) => {
        if (isMobile() && currentOpenPanel && !currentOpenPanel.contains(e.target) && e.target !== hamburgerBtn) {
            closeAllPanels();
        }
    });
    
    // Prevent clicks inside panels from closing them
    navColumn.addEventListener('click', (e) => e.stopPropagation());
    verseColumn.addEventListener('click', (e) => e.stopPropagation());
    
    // Handle window resize
    window.addEventListener('resize', () => {
        updateMobileVisibility();
        if (!isMobile()) {
            closeAllPanels();
        }
    });
    
    // Initial setup
    updateMobileVisibility();
}

// Valid model/record_level combinations
const VALID_COMBINATIONS = {
    'pericope': ['hebrew_st', 'english_st'],
    'verse': ['hebrew_st', 'berit', 'english_st'],
    'agentic_berit': ['berit', 'hebrew_st', 'english_st'],
    'agentic_hebrew_st': ['hebrew_st', 'english_st'],
    'agentic_english_st': ['hebrew_st', 'english_st'],
};

function validateSearchButton() {
    const modelName = document.querySelector("#model_name").value;
    const recordLevel = document.querySelector("#record_level").value;
    const searchButton = document.querySelector("#search_button");
    const searchVersesField = document.getElementById('search_verses');
    
    // Check if combination is valid
    const isValid = VALID_COMBINATIONS[recordLevel] && 
                    VALID_COMBINATIONS[recordLevel].includes(modelName);
    
    // Check if there are verses in the search field
    let hasVerses = false;
    try {
        const verses = JSON.parse(searchVersesField.value);
        hasVerses = Array.isArray(verses) && verses.length > 0;
    } catch (e) {
        hasVerses = false;
    }
    
    const canSearch = isValid && hasVerses;
    
    if (canSearch) {
        searchButton.disabled = false;
        searchButton.style.opacity = '1';
        searchButton.style.cursor = 'pointer';
        searchButton.title = '';
    } else {
        searchButton.disabled = true;
        searchButton.style.opacity = '0.6';
        searchButton.style.cursor = 'not-allowed';
        if (!isValid) {
            const validModels = VALID_COMBINATIONS[recordLevel] || [];
            searchButton.title = `Invalid combination. For ${recordLevel}, valid models are: ${validModels.join(', ')}`;
        } else if (!hasVerses) {
            searchButton.title = 'Please add verses to search';
        }
    }
}

function updateClearVersesButton() {
    const searchVersesField = document.getElementById('search_verses');
    const clearButton = document.getElementById('clear_verses_button');
    
    try {
        const verses = JSON.parse(searchVersesField.value);
        const hasVerses = Array.isArray(verses) && verses.length > 0;
        clearButton.disabled = !hasVerses;
        if (hasVerses) {
            clearButton.style.opacity = '1';
            clearButton.style.cursor = 'pointer';
        } else {
            clearButton.style.opacity = '0.6';
            clearButton.style.cursor = 'not-allowed';
        }
    } catch (e) {
        // If JSON is invalid, check if field is not empty
        const isEmpty = searchVersesField.value.trim() === '[]' || searchVersesField.value.trim() === '';
        clearButton.disabled = isEmpty;
        if (isEmpty) {
            clearButton.style.opacity = '0.6';
            clearButton.style.cursor = 'not-allowed';
        } else {
            clearButton.style.opacity = '1';
            clearButton.style.cursor = 'pointer';
        }
    }
}

function clearSearchVerses() {
    const searchVersesField = document.getElementById('search_verses');
    searchVersesField.value = '[]';
    selectedVerses.clear();
    // Update all checkboxes
    document.querySelectorAll('.verse-checkbox-item input[type="checkbox"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    document.querySelectorAll('.verse-checkbox-item').forEach(item => {
        item.classList.remove('selected');
    });
    updateClearVersesButton();
    validateSearchButton(); // Also validate search button when verses are cleared
}

let isFullScreen = false;

function toggleFullScreen() {
    const navColumn = document.getElementById('nav-column');
    const verseColumn = document.getElementById('verse-selection-column');
    const rightPanel = document.getElementById('right-panel');
    const resizer = document.getElementById('resizer');
    const leftPanel = document.getElementById('left-panel');
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    
    isFullScreen = !isFullScreen;
    
    if (isFullScreen) {
        // Hide navigation, verse selection, and search panels
        navColumn.style.display = 'none';
        verseColumn.style.display = 'none';
        rightPanel.style.display = 'none';
        resizer.style.display = 'none';
        leftPanel.style.width = '100%';
        fullscreenBtn.textContent = 'Exit Full Screen';
    } else {
        // Show all panels
        navColumn.style.display = '';
        verseColumn.style.display = '';
        rightPanel.style.display = 'block';
        resizer.style.display = 'block';
        leftPanel.style.width = `${savedLeftWidth}%`;
        rightPanel.style.width = `${100 - savedLeftWidth}%`;
        fullscreenBtn.textContent = 'Full Screen';
        
        // Update mobile visibility if needed
        if (window.innerWidth <= 600) {
            // On mobile, keep columns hidden by default
            navColumn.style.display = 'none';
            verseColumn.style.display = 'none';
        }
    }
}

async function performSearch() {
    console.log("performSearch");
    
    // Reset ratings for new search (only on dense page)
    if (isDensePage()) {
        resultRatings = {};
        currentResults = [];
        feedbackSubmitted = false;
        isSubmitting = false;
        
        // Reset submit button styling if it was transformed to a link
        const submitBtn = document.getElementById('submit-feedback-btn');
        if (submitBtn) {
            submitBtn.style.background = '';
            submitBtn.style.color = '';
            submitBtn.style.textDecoration = '';
            submitBtn.textContent = 'Submit';
            submitBtn.onclick = null; // Remove custom click handler
            
            // Re-attach the submit handler if it was removed
            if (!submitButtonHandler) {
                submitButtonHandler = handleFeedbackSubmit;
                submitBtn.addEventListener('click', submitButtonHandler);
            }
        }
    }
    
    // Clear results and show spinner immediately
    const container = document.querySelector("#results_container");
    container.innerHTML = '<div class="spinner-container"><div class="spinner"></div><div class="spinner-text">Searching...</div></div>';
    
    // Get form values
    const modelName = document.querySelector("#model_name").value;
    const recordLevel = document.querySelector("#record_level").value;
    const topK = document.querySelector("#top_k").value;
    const searchVersesStr = document.querySelector("#search_verses").value;
    
    // Validate combination (should already be validated by button state, but double-check)
    if (!VALID_COMBINATIONS[recordLevel] || !VALID_COMBINATIONS[recordLevel].includes(modelName)) {
        container.innerHTML = '<p style="color: red;">Invalid combination: ' + modelName + ' cannot be used with ' + recordLevel + '</p>';
        return;
    }
    
    // Validate search_verses JSON
    let searchVerses;
    try {
        searchVerses = JSON.parse(searchVersesStr);
    } catch (e) {
        container.innerHTML = '<p style="color: red;">Invalid JSON in Search Verses field: ' + e.message + '</p>';
        return;
    }
    
    // Build URL with query parameters
    const params = new URLSearchParams({
        model_name: modelName,
        record_level: recordLevel,
        top_k: topK,
        search_verses: JSON.stringify(searchVerses)
    });
    
    // For local testing: if on localhost (any port), use the functions-framework port (8080)
    // Otherwise use relative URL which will work with Firebase rewrites in production
    const isLocalhost = window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1' ||
                       window.location.hostname === '::1';
    // Always use localhost:8080 when testing locally (even if served from firebase on port 5000)
    const apiBase = isLocalhost ? 'http://localhost:8080' : '';
    const url = `${apiBase}/api/search?${params.toString()}`;
    console.log("Making request to: " + url);
    console.log("Hostname: " + window.location.hostname + ", isLocalhost: " + isLocalhost);
    
    try {
        let response = await fetch(url);
        console.log("handling response: " + response.status);
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || "Search failed");
        }
        
        let responseData = await response.json();
        console.log("Received response:", responseData);
        
        // Handle both old format (array) and new format (object with english_search_text)
        let results, englishSearchText;
        if (Array.isArray(responseData)) {
            results = responseData;
            englishSearchText = null;
        } else {
            results = responseData.results || [];
            englishSearchText = responseData.english_search_text;
        }
        
        displaySearchInfo(englishSearchText);
        displayResults(results);
        
    } catch (error) {
        console.error("Error performing search:", error);
        container.innerHTML = '<p style="color: red;">Error: ' + error.message + '</p>';
        // Reset on error (only on dense page)
        if (isDensePage()) {
            resultRatings = {};
            currentResults = [];
        }
    }
}

function formatVerses(versesStr) {
    try {
        const verses = typeof versesStr === 'string' ? JSON.parse(versesStr) : versesStr;
        if (!Array.isArray(verses) || verses.length === 0) return '';
        
        // Convert to array of {chapter, verse} objects and sort
        const verseObjs = verses.map(v => ({
            chapter: typeof v.chapter === 'number' ? v.chapter : parseInt(v.chapter),
            verse: typeof v.verse === 'number' ? v.verse : parseFloat(v.verse)
        })).sort((a, b) => {
            if (a.chapter !== b.chapter) return a.chapter - b.chapter;
            return a.verse - b.verse;
        });
        
        if (verseObjs.length === 0) return '';
        
        // Group consecutive verses
        const groups = [];
        let currentGroup = [verseObjs[0]];
        
        for (let i = 1; i < verseObjs.length; i++) {
            const prev = verseObjs[i - 1];
            const curr = verseObjs[i];
            
            // Check if consecutive (same chapter and verse number is next)
            const isConsecutive = prev.chapter === curr.chapter && 
                                 Math.floor(curr.verse) === Math.floor(prev.verse) + 1;
            
            if (isConsecutive) {
                currentGroup.push(curr);
            } else {
                groups.push(currentGroup);
                currentGroup = [curr];
            }
        }
        groups.push(currentGroup);
        
        // Format groups
        const formatted = groups.map(group => {
            if (group.length === 1) {
                return `${group[0].chapter}:${group[0].verse}`;
            } else {
                // Check if all in same chapter
                const sameChapter = group.every(v => v.chapter === group[0].chapter);
                if (sameChapter) {
                    return `${group[0].chapter}:${group[0].verse}-${group[group.length - 1].verse}`;
                } else {
                    // Mixed chapters, just join with commas
                    return group.map(v => `${v.chapter}:${v.verse}`).join(', ');
                }
            }
        }).join(', ');
        
        return formatted;
    } catch (e) {
        return String(versesStr);
    }
}

function displaySearchInfo(englishSearchText) {
    const container = document.querySelector("#results_container");
    let infoHtml = '';
    
    if (englishSearchText) {
        infoHtml = `<div class="search-info"><strong>Searching for:</strong> ${englishSearchText}</div>`;
    }
    
    // Store for later use in displayResults
    container.innerHTML = infoHtml;
}

function displayResults(results) {
    const container = document.querySelector("#results_container");
    const recordLevel = document.querySelector("#record_level").value;
    const topK = parseInt(document.querySelector("#top_k").value) || 10;
    
    // Store results globally (only on dense page)
    if (isDensePage()) {
        currentResults = results;
    }
    
    // Preserve search info if it exists
    const existingInfo = container.innerHTML;
    
    if (results.length === 0) {
        container.innerHTML = existingInfo + "<p>No results found.</p>";
        return;
    }
    
    // Only show verses field for pericope level
    const showVerses = recordLevel === 'pericope';
    
    // Only show feedback section if top_k >= 5 and we're on dense page
    const showFeedback = isDensePage() && topK >= 5;
    
    let html = existingInfo;
    
    // Add feedback section only if on dense page and top_k >= 5
    if (showFeedback) {
        html += `
            <div class="feedback-section">
                <div class="feedback-header">
                    <div class="feedback-label-group">
                        <div class="feedback-label-row">
                            <label class="feedback-label">
                                Provide Feedback:
                                <span class="info-icon-wrapper">
                                    <svg class="info-icon" xmlns="http://www.w3.org/2000/svg" height="14px" viewBox="0 -960 960 960" width="14px" fill="#999" title="Click for rating instructions">
                                        <path d="M440-280h80v-240h-80v240Zm40-320q17 0 28.5-11.5T520-640q0-17-11.5-28.5T480-680q-17 0-28.5 11.5T440-640q0 17 11.5 28.5T480-600Zm0 520q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z"/>
                                    </svg>
                                    <div class="info-tooltip">
                                        Rank each result based on if it Sparked Interesting Meditation.<br>
                                        - 5 is a really interesting spark<br>
                                        - 0 means the result had no value to you<br>
                                        Then if you are really excited about the meditation for the hyperlink, you can mark it as a 10 (mainly for fun, in the averages it scores a 10 as a 5, but 10 is fun sometimes). Or if you found a result inappropriate for any reason or it just shouldn't be there, mark it as a -1. Thanks for any feedback you have! BTW everything is fully anonymous.
                                    </div>
                                </span>
                            </label>
                            <button id="submit-feedback-btn" class="submit-feedback-btn" disabled>Submit</button>
                        </div>
                        <div class="feedback-subtitle">Rank the Top 5 Results</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Add results with rating dropdowns (only on top 5 if feedback is shown)
    for (let i = 0; i < results.length; i++) {
        const result = results[i];
        const currentRating = isDensePage() ? (resultRatings[i] || '') : '';
        const showRating = showFeedback && i < 5; // Only show rating on top 5
        
        let versesHtml = '';
        if (showVerses) {
            const formattedVerses = formatVerses(result.verses || "");
            if (formattedVerses) {
                versesHtml = `<div class="verses"><strong>Verses:</strong> ${formattedVerses}</div>`;
            }
        }
        
        html += `
            <div class="result-item" data-result-index="${i}">
                <div class="result-header">
                    <h3>${result.title || result.id}</h3>
                    ${showRating ? `
                    <select class="meditation-rating" data-result-index="${i}">
                        <option value="" ${currentRating === '' ? 'selected' : ''}></option>
                        <option value="10" ${currentRating === '10' ? 'selected' : ''}>10</option>
                        <option value="5" ${currentRating === '5' ? 'selected' : ''}>5</option>
                        <option value="4" ${currentRating === '4' ? 'selected' : ''}>4</option>
                        <option value="3" ${currentRating === '3' ? 'selected' : ''}>3</option>
                        <option value="2" ${currentRating === '2' ? 'selected' : ''}>2</option>
                        <option value="1" ${currentRating === '1' ? 'selected' : ''}>1</option>
                        <option value="0" ${currentRating === '0' ? 'selected' : ''}>0</option>
                        <option value="-1" ${currentRating === '-1' ? 'selected' : ''}>-1</option>
                    </select>
                    ` : ''}
                </div>
                ${versesHtml}
                <div class="score">Score: ${result.score.toFixed(4)}</div>
                <div class="text">${result.text || ""}</div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    
    // Attach event listeners to rating dropdowns (only on dense page)
    if (isDensePage()) {
        document.querySelectorAll('.meditation-rating').forEach(select => {
            select.addEventListener('change', (e) => {
                const index = parseInt(e.target.dataset.resultIndex);
                resultRatings[index] = e.target.value;
                updateSubmitButtonState();
            });
        });
        
        // Attach event listener to submit button
        const submitBtn = document.getElementById('submit-feedback-btn');
        if (submitBtn) {
            // Remove old handler if it exists
            if (submitButtonHandler) {
                submitBtn.removeEventListener('click', submitButtonHandler);
            }
            // Store reference and add new handler
            submitButtonHandler = handleFeedbackSubmit;
            submitBtn.addEventListener('click', submitButtonHandler);
        }
        
        // Setup info icon tooltip
        document.querySelectorAll('.info-icon').forEach(infoIcon => {
            infoIcon.addEventListener('mouseenter', () => {
                const tooltip = infoIcon.parentElement.querySelector('.info-tooltip');
                if (tooltip) {
                    tooltip.style.display = 'block';
                }
            });
            infoIcon.addEventListener('mouseleave', () => {
                const tooltip = infoIcon.parentElement.querySelector('.info-tooltip');
                if (tooltip) {
                    tooltip.style.display = 'none';
                }
            });
        });
        
        // Initialize submit button state
        updateSubmitButtonState();
    }
}

function updateSubmitButtonState() {
    if (!isDensePage()) return;
    
    const submitBtn = document.getElementById('submit-feedback-btn');
    if (!submitBtn) return;
    
    // If already submitted, transform button into a link to results page
    if (feedbackSubmitted) {
        // Change button to a link-styled button
        submitBtn.disabled = false;
        submitBtn.style.opacity = '1';
        submitBtn.style.cursor = 'pointer';
        submitBtn.style.background = 'none';
        submitBtn.style.color = '#4CAF50';
        submitBtn.style.textDecoration = 'underline';
        submitBtn.style.padding = '5px 15px';
        submitBtn.textContent = 'See Feedback Results';
        submitBtn.title = 'View all feedback results';
        
        // Remove the original event listener to prevent double submission
        if (submitButtonHandler) {
            submitBtn.removeEventListener('click', submitButtonHandler);
            submitButtonHandler = null;
        }
        
        // Replace click handler to navigate to results page
        submitBtn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            window.location.href = '/avraham-results.html';
        };
        return;
    }
    
    // Check if top 5 results are rated (no blank values)
    const top5Rated = Array.from({ length: Math.min(5, currentResults.length) }, (_, i) => i)
        .every(index => resultRatings[index] !== undefined && resultRatings[index] !== '');
    
    if (top5Rated) {
        submitBtn.disabled = false;
        submitBtn.style.opacity = '1';
        submitBtn.style.cursor = 'pointer';
        submitBtn.title = 'Submit your feedback';
    } else {
        submitBtn.disabled = true;
        submitBtn.style.opacity = '0.6';
        submitBtn.style.cursor = 'not-allowed';
        submitBtn.title = 'Must rank the top 5 to submit';
    }
}

async function handleFeedbackSubmit() {
    if (!isDensePage()) return;
    
    const submitBtn = document.getElementById('submit-feedback-btn');
    if (!submitBtn || submitBtn.disabled || isSubmitting || feedbackSubmitted) return;
    
    // Set flag to prevent double submission
    isSubmitting = true;
    
    // Disable button immediately to prevent double-submission
    submitBtn.disabled = true;
    submitBtn.style.opacity = '0.6';
    submitBtn.style.cursor = 'not-allowed';
    
    try {
        // Get current search parameters
        const modelName = document.querySelector("#model_name").value;
        const recordLevel = document.querySelector("#record_level").value; // Note: avraham-dense uses "record_level" not "chunking_level"
        const topK = parseInt(document.querySelector("#top_k").value) || 10;
        const searchVersesStr = document.querySelector("#search_verses").value;
        
        // Parse search_verses
        let searchVerses;
        try {
            searchVerses = JSON.parse(searchVersesStr);
        } catch (e) {
            console.error('Error parsing search_verses:', e);
            throw new Error('Invalid search verses format');
        }
        
        // Build results_and_ranking array (top 5 only)
        const resultsAndRanking = [];
        for (let i = 0; i < Math.min(5, currentResults.length); i++) {
            const result = currentResults[i];
            // Get rating - should be set since we require top 5 to be rated
            const ratingStr = resultRatings[i] || '';
            const rating = ratingStr !== '' ? parseInt(ratingStr) : 0;
            
            // Store the entire result object (all fields from server response)
            const resultMap = JSON.parse(JSON.stringify(result)); // Deep copy to avoid reference issues
            
            resultsAndRanking.push({
                rank: i + 1,
                result: resultMap,
                distance: result.score || 0.0,
                rating: rating
            });
        }
        
        // Build the Firestore document
        const feedbackDoc = {
            created: firebase.firestore.FieldValue.serverTimestamp(),
            endpoint: 'dense', // avraham-dense.html uses "dense" endpoint
            model_name: modelName,
            chunking_level: recordLevel, // Store as chunking_level in Firestore (for consistency with dense-2)
            top_k: topK,
            search_verses: searchVerses,
            results_and_ranking: resultsAndRanking
        };
        
        // Save to Firestore
        if (db) {
            await db.collection('SearchFeedback').add(feedbackDoc);
            console.log('Feedback saved to Firestore successfully');
        } else {
            console.warn('Firestore not initialized, skipping save');
        }
        
        // Mark as submitted
        feedbackSubmitted = true;
        
        // Show toast
        showToast('Results submitted. Thank you!');
        
        // Update button state (will show "Already submitted" tooltip)
        updateSubmitButtonState();
        
    } catch (error) {
        console.error('Error saving feedback to Firestore:', error);
        showToast('Error saving feedback. Please try again.');
        
        // Reset flags and re-enable button on error
        isSubmitting = false;
        submitBtn.disabled = false;
        submitBtn.style.opacity = '1';
        submitBtn.style.cursor = 'pointer';
    }
}

function showToast(message) {
    // Remove existing toast if any
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // Remove after animation
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
}

// Audio Player Functions
let audioPlayer = null;
let currentAudioFile = null;

function setupAudioPlayer() {
    audioPlayer = document.getElementById('audio-player');
    if (!audioPlayer) {
        console.warn('Audio player element not found');
        return;
    }
    
    const toggleBtn = document.getElementById('audio-player-toggle');
    const controls = document.getElementById('audio-player-controls');
    const playPauseBtn = document.getElementById('audio-play-pause');
    const jumpBack10Btn = document.getElementById('audio-jump-back-10');
    const jumpToSectionBtn = document.getElementById('audio-jump-to-section');
    const playIcon = document.getElementById('play-icon');
    const pauseIcon = document.getElementById('pause-icon');
    const progressSlider = document.getElementById('audio-progress');
    const currentTimeDisplay = document.getElementById('audio-current-time');
    const durationDisplay = document.getElementById('audio-duration');
    
    if (!toggleBtn || !controls || !playPauseBtn || !jumpToSectionBtn || !progressSlider) {
        console.warn('Audio player control elements not found');
        return;
    }
    
    // Toggle controls visibility with slide animation
    toggleBtn.addEventListener('click', () => {
        controls.classList.toggle('show');
    });
    
    // Play/Pause button
    playPauseBtn.addEventListener('click', () => {
        if (audioPlayer.paused) {
            audioPlayer.play().catch(err => {
                console.error('Error playing audio:', err);
            });
        } else {
            audioPlayer.pause();
        }
    });
    
    // Jump Back 10 seconds button
    if (jumpBack10Btn) {
        jumpBack10Btn.addEventListener('click', () => {
            if (audioPlayer && !isNaN(audioPlayer.currentTime)) {
                const newTime = Math.max(0, audioPlayer.currentTime - 10);
                audioPlayer.currentTime = newTime;
            }
        });
    }
    
    // Update play/pause icon based on audio state
    audioPlayer.addEventListener('play', () => {
        if (playIcon) playIcon.style.display = 'none';
        if (pauseIcon) pauseIcon.style.display = 'block';
    });
    
    audioPlayer.addEventListener('pause', () => {
        if (playIcon) playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
    });
    
    // Update progress slider and time displays
    function updateProgress() {
        if (!isSeeking && audioPlayer.duration) {
            const percent = (audioPlayer.currentTime / audioPlayer.duration) * 100;
            progressSlider.value = percent;
        }
        if (currentTimeDisplay) {
            currentTimeDisplay.textContent = formatTime(audioPlayer.currentTime);
        }
    }
    
    // Update duration when metadata loads
    audioPlayer.addEventListener('loadedmetadata', () => {
        if (durationDisplay && audioPlayer.duration) {
            durationDisplay.textContent = formatTime(audioPlayer.duration);
            progressSlider.max = 100;
        }
    });
    
    // Update progress as audio plays
    audioPlayer.addEventListener('timeupdate', updateProgress);
    
    // Auto-advance to next audio when current audio ends
    audioPlayer.addEventListener('ended', () => {
        // Find the next visual with audio
        let nextIndex = currentVisualIndex + 1;
        while (nextIndex < textVisuals.length) {
            const nextVisual = textVisuals[nextIndex];
            if (nextVisual.audio_file && nextVisual.audio_file !== '') {
                // Found next visual with audio, navigate to it
                // selectVisual will update the audio since it's paused (just ended)
                selectVisual(nextIndex);
                
                // Wait for audio metadata to load (updateAudioForCurrentVisual is async)
                // Then start playing automatically from the correct start_at time
                const startAt = nextVisual.start_at || 0;
                const playNextAudio = () => {
                    audioPlayer.currentTime = startAt;
                    audioPlayer.play().catch(err => {
                        console.error('Error auto-playing next audio:', err);
                    });
                };
                
                // Wait for loadedmetadata event (will fire when updateAudioForCurrentVisual loads the file)
                audioPlayer.addEventListener('loadedmetadata', playNextAudio, { once: true });
                
                // Also check if metadata is already loaded (same file case)
                if (audioPlayer.readyState >= 1) { // HAVE_METADATA
                    audioPlayer.removeEventListener('loadedmetadata', playNextAudio);
                    playNextAudio();
                }
                break;
            }
            nextIndex++;
        }
        // If no next audio found, do nothing (audio just stops)
    });
    
    // Allow seeking via progress slider
    let isSeeking = false;
    progressSlider.addEventListener('mousedown', () => {
        isSeeking = true;
    });
    progressSlider.addEventListener('mouseup', () => {
        isSeeking = false;
    });
    progressSlider.addEventListener('input', (e) => {
        if (audioPlayer.duration) {
            const percent = parseFloat(e.target.value);
            const newTime = (percent / 100) * audioPlayer.duration;
            audioPlayer.currentTime = newTime;
        }
    });
    
    // Jump to current section - FIXED to properly jump to start_at
    jumpToSectionBtn.addEventListener('click', () => {
        if (currentVisualIndex >= 0 && currentVisualIndex < textVisuals.length) {
            const visual = textVisuals[currentVisualIndex];
            if (visual.audio_file && visual.start_at !== undefined) {
                const audioPath = `audio/${visual.audio_file}`;
                const fullAudioPath = new URL(audioPath, window.location.href).href;
                
                // Check if we need to change the audio file
                if (!audioPlayer.src || audioPlayer.src !== fullAudioPath) {
                    // Need to load new file
                    const wasPlaying = !audioPlayer.paused;
                    audioPlayer.src = audioPath;
                    audioPlayer.load();
                    
                    audioPlayer.addEventListener('loadedmetadata', () => {
                        audioPlayer.currentTime = visual.start_at || 0;
                        if (wasPlaying) {
                            audioPlayer.play().catch(err => {
                                console.error('Error playing audio:', err);
                            });
                        }
                    }, { once: true });
                } else {
                    // Same file, just jump to start_at
                    audioPlayer.currentTime = visual.start_at || 0;
                }
            }
        }
    });
    
    // Initialize audio will be called after textVisuals are loaded
}

// Helper function to format time as MM:SS
function formatTime(seconds) {
    if (isNaN(seconds) || !isFinite(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function updateAudioForCurrentVisual() {
    if (currentVisualIndex < 0 || currentVisualIndex >= textVisuals.length) {
        return;
    }
    
    const visual = textVisuals[currentVisualIndex];
    
    // Check if this visual has audio
    if (!visual.audio_file || visual.audio_file === '') {
        // Hide audio player if no audio file
        document.getElementById('audio-player-container').style.display = 'none';
        return;
    }
    
    // Show audio player
    document.getElementById('audio-player-container').style.display = 'flex';
    
    // Update audio source if file changed
    const audioPath = `audio/${visual.audio_file}`;
    const fullAudioPath = new URL(audioPath, window.location.href).href;
    
    // Only update if the file actually changed
    if (!audioPlayer.src || audioPlayer.src !== fullAudioPath) {
        audioPlayer.src = audioPath;
        currentAudioFile = visual.audio_file;
        
        // Load the new audio
        audioPlayer.load();
        
        // Set start time after metadata loads
        audioPlayer.addEventListener('loadedmetadata', () => {
            const startAt = visual.start_at || 0;
            audioPlayer.currentTime = startAt;
        }, { once: true });
    }
    // Note: We don't change currentTime if the file hasn't changed
    // This allows audio to continue playing when navigating
}
