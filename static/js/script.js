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

    // Preset Buttons
    document.querySelectorAll('.preset-pill').forEach(pill => {
        pill.addEventListener('click', function () {
            document.querySelectorAll('.preset-pill').forEach(p => p.classList.remove('active'));
            this.classList.add('active');

            const threads = this.getAttribute('data-threads');
            const copies = this.getAttribute('data-copies');
            const mutex = this.getAttribute('data-mutex');

            if (threads) threadsInput.value = threads;
            if (copies) copiesInput.value = copies;
            if (mutex !== null) mutexToggle.checked = (mutex === 'true');
        });
    });

    // Reset Button Handler
    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            const copies = copiesInput.value || 1;
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
                    resetBtn.innerHTML = '<span>Reset Test Book</span>';
                    appendTerminalRow({
                        seq: '*',
                        timestamp: new Date().toLocaleTimeString(),
                        thread_name: 'Coordinator',
                        event_type: 'RESET',
                        details: `Test book state cleared. Fresh ${copies} copy(ies) created as AVAILABLE.`,
                        status_badge: 'UNLOCKED'
                    });
                    updateLockDisplay('UNLOCKED', null);
                    // Reload page or update copies display if needed
                    location.reload();
                })
                .catch(err => {
                    resetBtn.disabled = false;
                    resetBtn.innerHTML = '<span>Reset Test Book</span>';
                    alert('Error resetting test book: ' + err);
                });
        });
    }

    // Run Test Button Handler
    if (runBtn) {
        runBtn.addEventListener('click', function () {
            const numThreads = parseInt(threadsInput.value) || 2;
            const initialCopies = parseInt(copiesInput.value) || 1;
            const useMutex = mutexToggle.checked;

            runBtn.disabled = true;
            runBtn.innerHTML = '<span class="spinner"></span> <span>Running Threads...</span>';
            terminalBody.innerHTML = '';
            summaryCard.style.display = 'none';

            // Show active lock status
            updateLockDisplay('UNLOCKED', null);

            fetch('/concurrency-test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    num_threads: numThreads,
                    initial_copies: initialCopies,
                    use_mutex: useMutex,
                    book_id: 'B100'
                })
            })
                .then(res => res.json())
                .then(response => {
                    runBtn.disabled = false;
                    runBtn.innerHTML = '<span>Run Concurrency Test</span>';

                    if (response.success && response.data) {
                        displaySimulationResults(response.data);
                    } else {
                        alert("Concurrency test returned an unexpected error.");
                    }
                })
                .catch(err => {
                    runBtn.disabled = false;
                    runBtn.innerHTML = '<span>Run Concurrency Test</span>';
                    alert("Error executing concurrency test: " + err);
                });
        });
    }

    function displaySimulationResults(data) {
        const events = data.events || [];
        const status = data.status || {};

        // Play events in terminal with slight stagger for natural visual comprehension
        let delay = 0;
        events.forEach((evt, idx) => {
            setTimeout(() => {
                appendTerminalRow(evt);
                // Update lock visual dynamically based on event
                if (evt.event_type === 'LOCK_ACQUIRED' || evt.event_type === 'ENTERED_CRITICAL_SECTION') {
                    updateLockDisplay('LOCKED', evt.thread_name);
                } else if (evt.event_type === 'LOCK_RELEASED') {
                    updateLockDisplay('UNLOCKED', null);
                }
            }, delay);
            delay += 25; // Smooth stagger
        });

        // After all events animated, reveal the final summary card
        setTimeout(() => {
            updateLockDisplay('UNLOCKED', null);
            summaryCard.style.display = 'block';
            summaryText.textContent = status.summary_message;

            statThreads.textContent = status.total_threads;
            statInitialCopies.textContent = status.initial_copies;
            statSuccess.textContent = status.successful_issues;
            statBlocked.textContent = status.failed_requests;

            if (status.mutex_enabled) {
                if (status.invariants_passed) {
                    invariantBadge.className = 'badge badge-available';
                    invariantBadge.textContent = 'PASSED (NO RACE CONDITION)';
                } else {
                    invariantBadge.className = 'badge badge-cancelled';
                    invariantBadge.textContent = 'FAILED';
                }
            } else {
                invariantBadge.className = 'badge badge-locked';
                invariantBadge.textContent = 'RACE CONDITION TRIGGERED';
            }
        }, delay + 50);
    }

    function appendTerminalRow(evt) {
        const row = document.createElement('div');
        row.className = 'log-entry-row';

        let badgeClass = 'badge-available';
        if (evt.status_badge === 'WAITING') badgeClass = 'badge-waiting';
        else if (evt.status_badge === 'LOCKED' || evt.status_badge === 'DANGER') badgeClass = 'badge-locked';
        else if (evt.status_badge === 'CRITICAL') badgeClass = 'badge-critical';
        else if (evt.status_badge === 'UNAVAILABLE' || evt.status_badge === 'ERROR') badgeClass = 'badge-cancelled';
        else if (evt.status_badge === 'UNLOCKED') badgeClass = 'badge-unlocked';
        else if (evt.status_badge === 'ISSUED') badgeClass = 'badge-ready';

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
            if (lockSubtext) lockSubtext.textContent = `Held by ${holder || 'Active Thread'}`;
        } else {
            lockIndicator.className = 'lock-status-indicator unlocked';
            lockIndicator.innerHTML = '🔓';
            lockLabel.className = 'lock-state-label unlocked';
            lockLabel.textContent = 'UNLOCKED';
            if (lockSubtext) lockSubtext.textContent = 'Critical section free for acquisition';
        }
    }
}
