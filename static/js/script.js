/**
 * script.js - Client-Side Interactions & OS Concurrency Visualizer
 * Handles real-time search, modals, and the live multithreaded concurrency monitor.
 */

document.addEventListener('DOMContentLoaded', function () {
    initFlashAlerts();
    initCatalogueSearch();
    initModals();
    if (document.getElementById('concurrencyMonitorApp')) {
        initConcurrencyMonitor();
    }
});

// ==================== FLASH ALERTS ====================
function initFlashAlerts() {
    document.querySelectorAll('.alert-close').forEach(btn => {
        btn.addEventListener('click', function () {
            const alert = this.closest('.alert');
            if (alert) {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 250);
            }
        });
    });
}

// ==================== MODALS ====================
function initModals() {
    document.querySelectorAll('[data-modal-target]').forEach(trigger => {
        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('data-modal-target');
            const modal = document.getElementById(targetId);
            if (modal) {
                modal.classList.add('show');
            }
        });
    });

    document.querySelectorAll('.modal-close, .modal-backdrop').forEach(element => {
        element.addEventListener('click', function (e) {
            if (e.target === this) {
                const modal = this.closest('.modal-backdrop') || this;
                modal.classList.remove('show');
            }
        });
    });
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('show');
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('show');
}

// ==================== CATALOGUE SEARCH ====================
function initCatalogueSearch() {
    const searchInput = document.getElementById('bookSearchInput');
    const categoryFilter = document.getElementById('categoryFilter');
    const booksContainer = document.getElementById('booksGridContainer');

    if (!searchInput || !booksContainer) return;

    let debounceTimer;

    function performSearch() {
        const query = searchInput.value.trim();
        const category = categoryFilter ? categoryFilter.value : 'all';

        fetch(`/books/search?q=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    renderBookCards(data.books, booksContainer);
                }
            })
            .catch(err => console.error("Search error:", err));
    }

    searchInput.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(performSearch, 300);
    });

    if (categoryFilter) {
        categoryFilter.addEventListener('change', performSearch);
    }
}

function renderBookCards(books, container) {
    if (!books || books.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 3rem 1rem; background: white; border-radius: 12px; border: 1px dashed #CBD5E1;">
                <p style="font-size: 1.1rem; font-weight: 600; color: #475569;">No books found matching your criteria.</p>
                <p style="font-size: 0.85rem; color: #94A3B8; margin-top: 0.3rem;">Try adjusting your search query or selecting a different category.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = books.map(book => {
        const isDemo = book.book_id === 'B100';
        const isAvailable = (book.available_copies || 0) > 0;
        
        let actionBtn = '';
        if (isAvailable) {
            actionBtn = `
                <form action="/issue" method="POST" style="flex: 1;">
                    <input type="hidden" name="book_id" value="${book.book_id}">
                    <button type="submit" class="btn btn-primary btn-sm" style="width: 100%;">
                        <span>Issue Copy</span>
                    </button>
                </form>
            `;
        } else {
            actionBtn = `
                <form action="/reserve" method="POST" style="flex: 1;">
                    <input type="hidden" name="book_id" value="${book.book_id}">
                    <button type="submit" class="btn btn-teal btn-sm" style="width: 100%;">
                        <span>Reserve (${book.waiting_reservations || 0} waiting)</span>
                    </button>
                </form>
            `;
        }

        return `
            <div class="book-card">
                <div class="book-card-top ${isDemo ? 'demo-book-banner' : ''}">
                    <span class="book-category-tag">${book.category}</span>
                    <span class="book-id-badge">${book.book_id}</span>
                </div>
                <div class="book-card-body">
                    <h3 class="book-title">${book.title}</h3>
                    <p class="book-author">by ${book.author}</p>
                    <p class="book-description">${book.description || 'No description provided.'}</p>
                    
                    <div class="book-availability-bar">
                        <div class="copies-stat">
                            <span>Available: <strong>${book.available_copies || 0}</strong> / ${book.total_copies || 0}</span>
                        </div>
                        <span class="badge ${isAvailable ? 'badge-available' : 'badge-issued'}">
                            ${isAvailable ? 'AVAILABLE' : 'ALL ISSUED'}
                        </span>
                    </div>

                    <div class="book-card-actions">
                        ${actionBtn}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// ==================== OS CONCURRENCY MONITOR CONTROLLER ====================
function initConcurrencyMonitor() {
    const runBtn = document.getElementById('runTestBtn');
    const resetBtn = document.getElementById('resetTestBtn');
    const threadsInput = document.getElementById('testThreadsInput');
    const copiesInput = document.getElementById('testCopiesInput');
    const mutexToggle = document.getElementById('testMutexToggle');
    const bookSelect = document.getElementById('testBookSelect');
    const currentCopiesDisplay = document.getElementById('currentCopiesDisplay');
    const threadsBoardGrid = document.getElementById('threadsBoardGrid');
    const terminalBody = document.getElementById('terminalBody');
    const lockIndicator = document.getElementById('lockIndicator');
    const lockLabel = document.getElementById('lockLabel');
    const lockSubtext = document.getElementById('lockSubtext');
    const summaryCard = document.getElementById('summaryCard');
    const summaryText = document.getElementById('summaryText');
    const statThreads = document.getElementById('statThreads');
    const statInitialCopies = document.getElementById('statInitialCopies');
    const statSuccess = document.getElementById('statSuccess');
    const statBlocked = document.getElementById('statBlocked');
    const invariantBadge = document.getElementById('invariantBadge');

    // Initialize initial student cards (defaults to 5 students)
    const initialNumThreads = parseInt(threadsInput ? threadsInput.value : 5) || 5;
    renderStudentCards(initialNumThreads);

    // Book Select Dropdown Change Listener
    if (bookSelect) {
        bookSelect.addEventListener('change', function () {
            const selectedOpt = this.options[this.selectedIndex];
            const copies = selectedOpt.getAttribute('data-copies') || 1;
            if (currentCopiesDisplay) {
                currentCopiesDisplay.textContent = `${copies} Available`;
            }
            if (copiesInput) {
                copiesInput.value = copies;
            }
        });
    }

    // Number of Students Input Listener
    if (threadsInput) {
        threadsInput.addEventListener('change', function () {
            const count = Math.max(1, Math.min(20, parseInt(this.value) || 5));
            this.value = count;
            renderStudentCards(count);
        });
    }

    // Preset Buttons
    document.querySelectorAll('.preset-pill').forEach(pill => {
        pill.addEventListener('click', function () {
            document.querySelectorAll('.preset-pill').forEach(p => p.classList.remove('active'));
            this.classList.add('active');

            const threads = this.getAttribute('data-threads');
            const copies = this.getAttribute('data-copies');
            const mutex = this.getAttribute('data-mutex');

            if (threads && threadsInput) {
                threadsInput.value = threads;
                renderStudentCards(parseInt(threads));
            }
            if (copies && copiesInput) {
                copiesInput.value = copies;
                if (currentCopiesDisplay) {
                    currentCopiesDisplay.textContent = `${copies} Available`;
                }
            }
            if (mutex !== null && mutexToggle) {
                mutexToggle.checked = (mutex === 'true');
            }
        });
    });

    // Helper: Dynamically Render Student Thread Cards
    function renderStudentCards(count) {
        if (!threadsBoardGrid) return;
        threadsBoardGrid.innerHTML = '';
        for (let i = 1; i <= count; i++) {
            const card = document.createElement('div');
            card.className = 'student-thread-card state-waiting';
            card.id = `threadCard-${i}`;
            card.innerHTML = `
                <div class="thread-card-header">
                    <span class="thread-student-title">👤 Student ${i}</span>
                    <span class="badge badge-status-waiting" id="threadBadge-${i}">WAITING</span>
                </div>
                <div style="font-size: 0.78rem; color: var(--text-secondary);">
                    Thread ID: <code>Thread-${i}</code>
                </div>
                <div class="thread-step-box" id="threadStep-${i}">
                    Ready to request book copy...
                </div>
            `;
            threadsBoardGrid.appendChild(card);
        }
    }

    // Reset Button Handler
    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            const copies = copiesInput ? copiesInput.value || 1 : 1;
            resetBtn.disabled = true;
            resetBtn.innerHTML = '<span>Resetting...</span>';

            fetch('/concurrency-reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ initial_copies: parseInt(copies) })
            })
                .then(res => res.json())
                .then(data => {
                    resetBtn.disabled = false;
                    resetBtn.innerHTML = '<span>Reset Simulation</span>';
                    appendTerminalRow({
                        seq: '*',
                        timestamp: new Date().toLocaleTimeString(),
                        thread_name: 'System Coordinator',
                        event_type: 'RESET',
                        details: `Simulation reset. Fresh ${copies} copy(ies) created as AVAILABLE.`,
                        status_badge: 'UNLOCKED'
                    });
                    updateLockDisplay('UNLOCKED', null);
                    renderStudentCards(parseInt(threadsInput ? threadsInput.value : 5));
                    if (currentCopiesDisplay) currentCopiesDisplay.textContent = `${copies} Available`;
                    if (summaryCard) summaryCard.style.display = 'none';
                })
                .catch(err => {
                    resetBtn.disabled = false;
                    resetBtn.innerHTML = '<span>Reset Simulation</span>';
                    alert('Error resetting simulation: ' + err);
                });
        });
    }

    // Start Simulation Button Handler
    if (runBtn) {
        runBtn.addEventListener('click', function () {
            const numThreads = parseInt(threadsInput.value) || 5;
            const initialCopies = parseInt(copiesInput.value) || 1;
            const useMutex = mutexToggle.checked;
            const selectedBook = bookSelect ? bookSelect.value : 'B100';

            runBtn.disabled = true;
            runBtn.innerHTML = '<span class="spinner"></span> <span>Running Threads...</span>';
            terminalBody.innerHTML = '';
            if (summaryCard) summaryCard.style.display = 'none';

            // Reset cards to waiting state
            renderStudentCards(numThreads);
            updateLockDisplay('UNLOCKED', null);

            fetch('/concurrency-test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    num_threads: numThreads,
                    initial_copies: initialCopies,
                    use_mutex: useMutex,
                    book_id: selectedBook
                })
            })
                .then(res => res.json())
                .then(response => {
                    runBtn.disabled = false;
                    runBtn.innerHTML = '<span>Start Simulation (Run Threads)</span>';

                    if (response.success && response.data) {
                        displaySimulationResults(response.data);
                    } else {
                        alert("Concurrency test returned an unexpected error.");
                    }
                })
                .catch(err => {
                    runBtn.disabled = false;
                    runBtn.innerHTML = '<span>Start Simulation (Run Threads)</span>';
                    alert("Error executing concurrency test: " + err);
                });
        });
    }

    function displaySimulationResults(data) {
        const events = data.events || [];
        const status = data.status || {};

        // Play events with smooth stagger to visually see thread transitions
        let delay = 0;
        events.forEach((evt, idx) => {
            setTimeout(() => {
                appendTerminalRow(evt);

                // Update individual student thread visual card
                const threadId = evt.thread_id;
                if (threadId > 0) {
                    updateStudentCard(threadId, evt);
                }

                // Update lock visual dynamically based on event
                if (evt.event_type === 'MUTEX_ACQUIRED' || evt.event_type === 'ENTERED_CRITICAL_SECTION' || evt.event_type === 'LOCK_ACQUIRED') {
                    updateLockDisplay('LOCKED', evt.thread_name);
                } else if (evt.event_type === 'MUTEX_RELEASED' || evt.event_type === 'LOCK_RELEASED') {
                    updateLockDisplay('UNLOCKED', null);
                }
            }, delay);
            delay += 45; // Smooth stagger
        });

        // After all events animated, reveal the final summary card
        setTimeout(() => {
            updateLockDisplay('UNLOCKED', null);
            if (summaryCard) summaryCard.style.display = 'block';
            if (summaryText) summaryText.textContent = status.summary_message;

            if (statThreads) statThreads.textContent = status.total_threads;
            if (statInitialCopies) statInitialCopies.textContent = status.initial_copies;
            if (statSuccess) statSuccess.textContent = status.successful_issues;
            if (statBlocked) statBlocked.textContent = status.failed_requests;

            if (status.mutex_enabled) {
                if (status.invariants_passed) {
                    invariantBadge.className = 'badge badge-status-completed';
                    invariantBadge.textContent = 'PASSED (MUTUAL EXCLUSION ENFORCED)';
                } else {
                    invariantBadge.className = 'badge badge-status-failed';
                    invariantBadge.textContent = 'FAILED';
                }
            } else {
                invariantBadge.className = 'badge badge-status-locked';
                invariantBadge.textContent = 'RACE CONDITION DEMONSTRATED';
            }

            // Update remaining copies display
            if (currentCopiesDisplay) {
                const remaining = Math.max(0, status.initial_copies - status.successful_issues);
                currentCopiesDisplay.textContent = `${remaining} Available`;
            }
        }, delay + 60);
    }

    function updateStudentCard(threadId, evt) {
        const card = document.getElementById(`threadCard-${threadId}`);
        const badge = document.getElementById(`threadBadge-${threadId}`);
        const step = document.getElementById(`threadStep-${threadId}`);

        if (!card || !badge || !step) return;

        const eventType = evt.event_type;

        if (eventType === 'THREAD_CREATED') {
            badge.className = 'badge badge-status-waiting';
            badge.textContent = 'WAITING';
            step.textContent = 'Thread Initialized';
        } else if (eventType === 'THREAD_STARTED') {
            card.className = 'student-thread-card state-running';
            badge.className = 'badge badge-status-running';
            badge.textContent = 'RUNNING';
            step.textContent = 'Thread Started. Arrived at Barrier.';
        } else if (eventType === 'WAITING_FOR_MUTEX' || eventType === 'WAITING_FOR_LOCK') {
            card.className = 'student-thread-card state-waiting';
            badge.className = 'badge badge-status-waiting';
            badge.textContent = 'WAITING';
            step.textContent = 'Waiting for Mutex Lock...';
        } else if (eventType === 'MUTEX_ACQUIRED' || eventType === 'LOCK_ACQUIRED' || eventType === 'ENTERED_CRITICAL_SECTION') {
            card.className = 'student-thread-card state-locked';
            badge.className = 'badge badge-status-locked';
            badge.textContent = 'LOCKED';
            step.textContent = 'Mutex Acquired! In Critical Section.';
        } else if (eventType === 'CHECKING_AVAILABILITY') {
            step.textContent = 'Checking copy availability in SQLite...';
        } else if (eventType === 'BOOK_ISSUED' || eventType === 'ISSUE_SUCCESS') {
            card.className = 'student-thread-card state-completed';
            badge.className = 'badge badge-status-completed';
            badge.textContent = 'COMPLETED';
            step.textContent = evt.details || 'Book Issued Successfully!';
        } else if (eventType.includes('RACE')) {
            card.className = 'student-thread-card state-locked';
            badge.className = 'badge badge-status-locked';
            badge.textContent = 'RACE COLLISION';
            step.textContent = evt.details || 'Unsafe concurrent assignment!';
        } else if (eventType === 'BOOK_UNAVAILABLE' || eventType === 'NO_COPY_AVAILABLE') {
            card.className = 'student-thread-card state-failed';
            badge.className = 'badge badge-status-failed';
            badge.textContent = 'FAILED';
            step.textContent = 'Book Unavailable (0 copies left)';
        } else if (eventType === 'THREAD_COMPLETED') {
            // Keep completed or failed status
            if (!badge.textContent.includes('COMPLETED') && !badge.textContent.includes('FAILED')) {
                step.textContent = 'Thread execution finished.';
            }
        }
    }

    function appendTerminalRow(evt) {
        const row = document.createElement('div');
        row.className = 'log-entry-row';

        let badgeClass = 'badge-available';
        if (evt.status_badge === 'WAITING') badgeClass = 'badge-waiting';
        else if (evt.status_badge === 'LOCKED' || evt.status_badge === 'DANGER') badgeClass = 'badge-locked';
        else if (evt.status_badge === 'CRITICAL' || evt.status_badge === 'RUNNING') badgeClass = 'badge-critical';
        else if (evt.status_badge === 'UNAVAILABLE' || evt.status_badge === 'ERROR' || evt.status_badge === 'FAILED') badgeClass = 'badge-cancelled';
        else if (evt.status_badge === 'UNLOCKED') badgeClass = 'badge-unlocked';
        else if (evt.status_badge === 'ISSUED' || evt.status_badge === 'COMPLETED') badgeClass = 'badge-ready';

        row.innerHTML = `
            <span class="log-seq">#${evt.seq}</span>
            <span class="log-time">${evt.timestamp}</span>
            <span class="log-thread">${evt.thread_name}</span>
            <span class="log-event"><span class="badge ${badgeClass}">${evt.event_type}</span></span>
            <span class="log-details">${evt.details}</span>
        `;

        terminalBody.appendChild(row);
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }

    function updateLockDisplay(state, holder) {
        if (!lockIndicator || !lockLabel) return;

        if (state === 'LOCKED') {
            lockIndicator.className = 'lock-status-indicator locked';
            lockIndicator.innerHTML = '🔒';
            lockLabel.className = 'lock-state-label locked';
            lockLabel.textContent = 'LOCKED';
            if (lockSubtext) lockSubtext.textContent = `Held by ${holder || 'Active Student Thread'}`;
        } else {
            lockIndicator.className = 'lock-status-indicator unlocked';
            lockIndicator.innerHTML = '🔓';
            lockLabel.className = 'lock-state-label unlocked';
            lockLabel.textContent = 'UNLOCKED';
            if (lockSubtext) lockSubtext.textContent = 'Critical section free for acquisition';
        }
    }
}

// ==================== CODE EDITOR TAB SWITCHER & COPY HELPER ====================
function switchCodeTab(tabId) {
    document.querySelectorAll('.code-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });
    document.querySelectorAll('.code-tab-pane').forEach(pane => {
        pane.classList.toggle('active', pane.id === tabId);
    });
}

function copyActiveCode() {
    const activePane = document.querySelector('.code-tab-pane.active .code-raw');
    if (activePane) {
        const text = activePane.value || activePane.textContent;
        navigator.clipboard.writeText(text.trim()).then(() => {
            const btn = document.getElementById('copyCodeBtn');
            if (btn) {
                const originalHtml = btn.innerHTML;
                btn.innerHTML = '<span>✅ Copied to Clipboard!</span>';
                setTimeout(() => { btn.innerHTML = originalHtml; }, 2000);
            }
        }).catch(err => {
            console.error('Copy failed:', err);
        });
    }
}

