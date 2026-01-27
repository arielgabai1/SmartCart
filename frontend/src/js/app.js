/**
 * SmartCart Helper Application
 * Monolithic script handling Auth, API, State, and UI logic.
 */

// --- Configuration ---

const CONFIG = {
    API_BASE: '/api',
    POLLING_INTERVAL: 3000
};

// --- State Management ---

const STATE = {
    user: null,
    items: [],
    members: [],
    lastItemsHash: null,
    lastMembersHash: null,
    isSubmitting: false
};

// --- Auth Service ---

const AuthService = {
    /** Retrieve JWT from storage */
    getToken: () => localStorage.getItem('sc_token'),

    /** Logout and redirect */
    logout: () => {
        localStorage.removeItem('sc_token');
        window.location.href = 'login.html';
    },

    /** Decode stored JWT to get user info */
    getUser: () => {
        const token = AuthService.getToken();
        if (!token) return null;
        try {
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            return JSON.parse(atob(base64));
        } catch (e) {
            console.error('JWT parse error:', e);
            return null;
        }
    },

    /** Check if session is valid */
    isAuthenticated: () => {
        const user = AuthService.getUser();
        return user && user.exp * 1000 > Date.now();
    }
};

// --- API Service ---

/**
 * authenticated fetch wrapper
 * @param {string} url - endpoint URL
 * @param {Object} options - fetch options
 */
async function secureFetch(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${AuthService.getToken()}`,
        ...options.headers
    };

    try {
        const res = await fetch(url, { ...options, headers });
        if (res.status === 401) {
            AuthService.logout();
        }
        return res;
    } catch (e) {
        console.error('Network error:', e);
        throw e;
    }
}

// --- Initialization ---

document.addEventListener('DOMContentLoaded', () => {
    if (!AuthService.isAuthenticated()) {
        AuthService.logout();
        return;
    }

    STATE.user = AuthService.getUser();
    initTheme();
    initUI();
    setupEventListeners();
    startPolling();
});

/** Initialize Theme (Light/Dark) */
function initTheme() {
    const savedTheme = localStorage.getItem('sc_theme');
    const isDark = savedTheme === 'dark';

    // Toggle class based on saved preference (defaulting to light if null/light)
    if (isDark) {
        document.body.classList.remove('light-mode');
    } else {
        document.body.classList.add('light-mode');
    }
    updateThemeIcon(!isDark);
}

/** Update Theme Icon SVG */
function updateThemeIcon(isLight) {
    const icon = document.getElementById('theme-icon');
    if (!icon) return;

    if (isLight) {
        // Sun icon
        icon.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
    } else {
        // Moon icon
        icon.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    }
}

/** Initialize Static UI Elements */
function initUI() {
    // Header Info
    setText('user-name-display', STATE.user.user_name || 'User');
    setText('group-name-display', STATE.user.group_name || 'My Group');
    setText('sidebar-join-code', STATE.user.join_code || '------');

    // Role Badge
    const userRoleEl = document.getElementById('user-role-display');
    if (userRoleEl) {
        userRoleEl.textContent = STATE.user.role;
        userRoleEl.style.color = STATE.user.role === 'MANAGER' ? 'var(--accent-info)' : 'var(--accent-success)';
    }

    // Avatar
    const userAvatarEl = document.getElementById('user-avatar');
    if (userAvatarEl) {
        userAvatarEl.textContent = (STATE.user.user_name || 'U').charAt(0).toUpperCase();
    }

    // Role-based Element Visibility
    const isManager = STATE.user.role === 'MANAGER';

    setDisplay('clear-all-btn', isManager ? 'flex' : 'none');
    setDisplay('members-section', 'block'); // Visible for all roles

    setText('form-title', isManager ? 'Add New Item' : 'Request Item');
    setText('submit-btn', isManager ? 'Add Item' : 'Submit Request');
}

// --- Event Listeners ---

function setupEventListeners() {
    // Sidebar
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    const toggleSidebar = (show) => {
        if (show) {
            sidebar?.classList.add('open');
            overlay?.classList.add('active');
            document.body.style.overflow = 'hidden';
        } else {
            sidebar?.classList.remove('open');
            overlay?.classList.remove('active');
            document.body.style.overflow = '';
        }
    };

    document.getElementById('menu-toggle')?.addEventListener('click', () => toggleSidebar(true));
    document.getElementById('sidebar-close')?.addEventListener('click', () => toggleSidebar(false));
    overlay?.addEventListener('click', () => toggleSidebar(false));

    // Clipboard with inline feedback (Unified)
    document.getElementById('copy-btn')?.addEventListener('click', async (e) => {
        // Handle child clicks
        const btn = e.target.closest('button');
        if (!btn) return;

        const code = STATE.user.join_code;
        if (!code) return;

        // Robust Copy Function
        const copyText = async (text) => {
            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(text);
                    return true;
                }
            } catch (err) { }

            // Fallback
            try {
                const textArea = document.createElement("textarea");
                textArea.value = text;
                textArea.style.position = "fixed";
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                const successful = document.execCommand('copy');
                document.body.removeChild(textArea);
                return successful;
            } catch (err) { return false; }
        };

        const success = await copyText(code);
        if (success) {
            // Visual Feedback: Checkmark Animation
            const originalText = btn.innerHTML; // Use innerHTML to preserve potential icons
            btn.innerHTML = '&#10003;'; // Checkmark symbol
            btn.classList.add('copied');

            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.classList.remove('copied');
            }, 3000); // 3 Seconds
        } else {
            showToast(`Code: ${code}`, 'info'); // Ultimate fallback
        }
    });

    // Auth
    document.getElementById('logout-btn')?.addEventListener('click', () => {
        if (confirm('Sign out?')) AuthService.logout();
    });

    // Forms
    document.getElementById('item-form')?.addEventListener('submit', handleFormSubmit);
    document.getElementById('clear-all-btn')?.addEventListener('click', deleteAllItems);

    // Theme
    document.getElementById('theme-toggle')?.addEventListener('click', () => {
        const isLight = document.body.classList.toggle('light-mode');
        localStorage.setItem('sc_theme', isLight ? 'light' : 'dark');
        updateThemeIcon(isLight);
    });
}

// --- Data Fetching ---

/** Fetch and refresh items list */
async function fetchItems() {
    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/items`, { cache: 'no-store' });
        if (!response.ok) return;

        const items = await response.json();
        const hash = JSON.stringify(items);

        // Update only if data changed
        if (hash !== STATE.lastItemsHash) {
            STATE.items = items;
            STATE.lastItemsHash = hash;
            renderItems();
            updateStats();
        }
    } catch (err) {
        console.error('Fetch items error:', err);
    }
}

/** Fetch and refresh members (All roles) */
async function fetchMembers(forceRefresh = false) {
    // if (STATE.user.role !== 'MANAGER') return; // Allow all to see members

    try {
        const url = `${CONFIG.API_BASE}/groups/members${forceRefresh ? '?t=' + Date.now() : ''}`;
        const response = await secureFetch(url, { cache: 'no-store' });
        if (!response.ok) return;

        const members = await response.json();
        const hash = JSON.stringify(members);

        if (hash !== STATE.lastMembersHash) {
            STATE.members = members;
            STATE.lastMembersHash = hash;
            renderMembers();
        }
    } catch (err) {
        console.error('Fetch members error:', err);
    }
}

/** Sync user role/data from server */
async function syncUserIdentity() {
    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/auth/me`, { cache: 'no-store' });
        if (!response.ok) return;

        const freshUser = await response.json();
        const roleChanged = freshUser.role !== STATE.user.role;

        STATE.user = { ...STATE.user, ...freshUser };

        if (roleChanged) {
            console.log(`Role updated: ${freshUser.role}`);
            initUI(); // Re-bind UI elements
            updateStats(); // Re-check pending section visibility

            if (freshUser.role === 'MANAGER') fetchMembers(true);
        }
    } catch (err) {
        console.error('Identity sync error:', err);
    }
}

// --- Item Logic ---

/** Handle new item submission */
async function handleFormSubmit(e) {
    e.preventDefault();
    if (STATE.isSubmitting) return;

    const nameInput = document.getElementById('name');
    const categoryInput = document.getElementById('category');
    const quantityInput = document.getElementById('quantity');

    const name = nameInput.value.trim();
    if (!name) return;

    STATE.isSubmitting = true;

    // Optimistic payload
    const payload = {
        name,
        category: categoryInput.value,
        quantity: parseInt(quantityInput.value) || 1
    };

    // Prepare rollback state
    const originalItems = [...STATE.items];

    // Optimistic UI Update
    STATE.items.push({
        _id: 'temp-' + Date.now(),
        ...payload,
        price_nis: 0,
        status: STATE.user.role === 'MANAGER' ? 'APPROVED' : 'PENDING',
        submitted_by: STATE.user.user_id,
        submitted_by_name: STATE.user.user_name || 'Me',
        ai_status: 'CALCULATING',
        created_at: new Date().toISOString()
    });

    renderItems();
    updateStats();

    // Reset form
    nameInput.value = '';
    quantityInput.value = '1';

    try {
        const res = await secureFetch(`${CONFIG.API_BASE}/items`, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error('API Error');
        await fetchItems(); // Sync real data

    } catch (err) {
        console.error('Submit error:', err);
        STATE.items = originalItems; // Rollback
        renderItems();
        updateStats();
        alert('Failed to add item. Please try again.');

        // Restore input
        nameInput.value = name;
    } finally {
        STATE.isSubmitting = false;
    }
}

/** Update status (Approve/Reject) */
async function updateItemStatus(itemId, newStatus) {
    try {
        const res = await secureFetch(`${CONFIG.API_BASE}/items/${itemId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: newStatus })
        });
        if (res.ok) fetchItems();
    } catch (err) { console.error(err); }
}

/** Update quantity */
async function updateQuantity(itemId, currentQty, delta) {
    const newQty = currentQty + delta;
    if (newQty < 1) return;

    try {
        const res = await secureFetch(`${CONFIG.API_BASE}/items/${itemId}`, {
            method: 'PUT',
            body: JSON.stringify({ quantity: newQty })
        });
        if (res.ok) fetchItems();
    } catch (err) { console.error(err); }
}

/** Delete item */
async function deleteItem(itemId) {
    if (!confirm('Delete this item?')) return;

    // Optimistic removal
    const original = [...STATE.items];
    STATE.items = STATE.items.filter(i => i._id !== itemId);
    renderItems();

    try {
        const res = await secureFetch(`${CONFIG.API_BASE}/items/${itemId}`, { method: 'DELETE' });
        if (!res.ok && res.status !== 404) throw new Error('Delete failed');
        fetchItems();
    } catch (err) {
        console.error(err);
        STATE.items = original;
        renderItems();
        alert('Could not delete item.');
    }
}

/** Clear all items (Manager) */
async function deleteAllItems() {
    if (!confirm('Clear the entire shopping list?')) return;
    try {
        const res = await secureFetch(`${CONFIG.API_BASE}/items/clear`, { method: 'DELETE' });
        if (res.ok) fetchItems();
    } catch (err) { console.error(err); }
}

// --- Member Logic ---

async function manageMember(userId, action, payload = {}) {
    try {
        const res = await secureFetch(`${CONFIG.API_BASE}/groups/members/${userId}`, {
            method: action,
            body: action === 'PUT' ? JSON.stringify(payload) : undefined
        });

        if (res.ok) {
            if (action === 'PUT') window.location.reload(); // Reload for permission sync
            else fetchMembers();
        } else {
            const err = await res.json();
            alert(`Action failed: ${err.error}`);
        }
    } catch (e) { console.error(e); }
}

window.promoteMember = (id) => confirm('Promote to Manager?') && manageMember(id, 'PUT', { role: 'MANAGER' });
window.demoteMember = (id) => confirm('Demote to Member?') && manageMember(id, 'PUT', { role: 'MEMBER' });
window.removeMember = (id) => confirm('Remove member?') && manageMember(id, 'DELETE');

// Expose functions globally for HTML onclick handlers
window.updateItemStatus = updateItemStatus;
window.updateQuantity = updateQuantity;
window.deleteItem = deleteItem;

// --- Rendering ---

function renderItems() {
    const container = document.getElementById('items-container');
    if (!container) return;

    const { role, user_id } = STATE.user;
    const items = STATE.items;

    const approved = items.filter(i => i.status === 'APPROVED');
    const pending = items.filter(i => i.status === 'PENDING');
    const rejected = items.filter(i => i.status === 'REJECTED');

    // 1. My Submissions Section (Non-Managers)
    if (role !== 'MANAGER') {
        const myItems = items.filter(i => i.submitted_by === user_id && ['PENDING', 'REJECTED'].includes(i.status));
        renderList('my-items-container', myItems, (item) => renderItemCard(item, false, true));
        setDisplay('my-items-section', myItems.length > 0 ? 'block' : 'none');
    }

    // 2. Pending Section (Manager Only)
    if (role === 'MANAGER') {
        renderList('pending-container', pending, (item) => renderItemCard(item, true, false));
    }

    // 3. Main List
    // Managers see Approved + Rejected (history), Members see Approved only
    const mainList = role === 'MANAGER' ? [...approved, ...rejected] : approved;

    if (mainList.length === 0) {
        container.innerHTML = `
            <div class="empty-state fade-in">
                <div class="empty-state-icon">&#128722;</div>
                <p class="empty-state-text">No items yet. Add your first item!</p>
            </div>`;
    } else {
        container.innerHTML = mainList.map(item => renderItemCard(item, false, false)).join('');
    }
}

function renderList(containerId, items, renderFn) {
    const el = document.getElementById(containerId);
    if (!el) return;

    if (items.length === 0) {
        el.innerHTML = '<p class="text-muted" style="padding: 1rem;">No items.</p>';
        return;
    }
    el.innerHTML = items.map(renderFn).join('');
}

function renderItemCard(item, isPending, isMyItem) {
    const total = ((item.price_nis || 0) * (item.quantity || 1)).toFixed(2);
    const isError = item.ai_status === 'ERROR';
    const isCalc = item.ai_status === 'CALCULATING';

    const showStatus = isMyItem || !isPending;
    const submitter = escapeHtml(item.submitted_by_name || 'Member');

    // Rejection details
    const isRejected = item.status === 'REJECTED';
    const rejectedBy = item.rejected_by_name ? ` by ${escapeHtml(item.rejected_by_name)}` : '';

    // Manager Actions
    const managerActions = STATE.user.role === 'MANAGER' ? `
        ${isPending ? `
            <button class="btn btn-success btn-sm" onclick="updateItemStatus('${item._id}', 'APPROVED')">Approve</button>
            <button class="btn btn-danger btn-sm" onclick="updateItemStatus('${item._id}', 'REJECTED')">Reject</button>
        ` : ''}
        <button class="btn btn-ghost btn-sm" onclick="deleteItem('${item._id}')">Delete</button>
    ` : '';

    // My Item Actions (Remove rejected)
    const myActions = (isMyItem && item.status === 'REJECTED') ? `
        <button class="btn btn-ghost btn-sm" onclick="deleteItem('${item._id}')">Remove</button>
    ` : '';

    return `
        <div class="item-card fade-in">
            <div class="item-header">
                <div>
                    <div class="item-title">${escapeHtml(item.name)}</div>
                    <div class="item-submitter">by ${submitter}</div>
                </div>
                ${showStatus ? `<span class="status-pill status-${item.status}">${item.status}${isRejected ? rejectedBy : ''}</span>` : ''}
            </div>
            <div class="item-footer">
                <div class="item-meta">
                    <span class="meta-tag">${item.category || 'OTHER'}</span>
                    <div class="quantity-control">
                        ${(STATE.user.role === 'MANAGER' || (isPending && isMyItem)) ?
            `<button class="quantity-btn" onclick="updateQuantity('${item._id}', ${item.quantity}, -1)">-</button>` : ''}
                        <span class="quantity-value">${item.quantity}</span>
                        ${(STATE.user.role === 'MANAGER' || (isPending && isMyItem)) ?
            `<button class="quantity-btn" onclick="updateQuantity('${item._id}', ${item.quantity}, 1)">+</button>` : ''}
                    </div>
                    ${isCalc ? '<span class="text-muted">Calculating...</span>' :
            isError ? '<span class="price-error">Price unavailable</span>' :
                `<span class="price-tag">${total} NIS</span>`}
                </div>
                <div class="item-actions">
                    ${managerActions || myActions}
                </div>
            </div>
        </div>
    `;
}

function renderMembers() {
    const container = document.getElementById('members-list');
    if (!container || !STATE.members.length) {
        if (container) container.innerHTML = '<p class="text-muted">No members.</p>';
        return;
    }

    container.innerHTML = STATE.members.map(m => {
        // Strict ID comparison fix - ensure both are strings
        const isMe = String(m.id) === String(STATE.user.user_id);
        const isMgr = m.role === 'MANAGER';
        const amIManager = STATE.user.role === 'MANAGER';

        let actionHtml = '';
        if (isMe) {
            actionHtml = '<span class="text-muted text-sm">You</span>';
        } else if (amIManager) {
            actionHtml = `
                <div class="member-actions">
                    <button class="btn btn-sm btn-ghost" onclick="${isMgr ? 'demoteMember' : 'promoteMember'}('${m.id}')">
                        ${isMgr ? 'Demote' : 'Promote'}
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="removeMember('${m.id}')">Remove</button>
                </div>
            `;
        }

        return `
            <div class="member-card">
                <div class="member-info">
                    <div class="member-name">${escapeHtml(m.user_name)}</div>
                    <div class="member-meta">${escapeHtml(m.email)} | ${m.role}</div>
                </div>
                ${actionHtml}
            </div>
        `;
    }).join('');
}

function updateStats() {
    const approved = STATE.items.filter(i => i.status === 'APPROVED');
    const pending = STATE.items.filter(i => i.status === 'PENDING');

    const total = approved.reduce((sum, i) => sum + ((i.price_nis || 0) * (i.quantity || 1)), 0);

    setText('cart-total', `${total.toFixed(2)} NIS`);
    setText('approved-count', approved.length);
    setText('pending-count', pending.length);

    // Toggle Pending Section Visibility
    const pendingSection = document.getElementById('pending-section');
    if (pendingSection) {
        pendingSection.style.display = (STATE.user.role === 'MANAGER' && pending.length > 0) ? 'block' : 'none';
    }
}

// --- Utils ---

// --- Utils ---

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast';

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';

    toast.innerHTML = `<span class="toast-icon">${icon}</span> ${escapeHtml(message)}`;
    container.appendChild(toast);

    // Auto remove
    setTimeout(() => {
        toast.classList.add('hiding');
        toast.addEventListener('animationend', () => toast.remove());
    }, 3000);
}

// Global Quantity Adjuster for Form
window.adjustFormQty = (delta) => {
    const input = document.getElementById('quantity');
    if (!input) return;
    let val = parseInt(input.value) || 1;
    val += delta;
    if (val < 1) val = 1;
    input.value = val;
};

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function setDisplay(id, display) {
    const el = document.getElementById(id);
    if (el) el.style.display = display;
}

function startPolling() {
    fetchItems();
    fetchMembers();
    syncUserIdentity();

    setInterval(() => {
        if (!document.hidden && !STATE.isSubmitting) {
            fetchItems();
            fetchMembers();
            syncUserIdentity();
        }
    }, CONFIG.POLLING_INTERVAL);
}