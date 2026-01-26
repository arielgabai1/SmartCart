const CONFIG = {
    API_BASE: '/api',
    POLLING_INTERVAL: 3000
};

const STATE = {
    user: null,
    items: [],
    members: [],
    lastItemsHash: null,
    lastMembersHash: null
};

// ==================== AUTH SERVICE ====================
const AuthService = {
    getToken: () => localStorage.getItem('sc_token'),

    logout: () => {
        localStorage.removeItem('sc_token');
        window.location.href = 'login.html';
    },

    getUser: () => {
        const token = AuthService.getToken();
        if (!token) return null;
        try {
            const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
            return payload;
        } catch (e) {
            console.error('JWT parse error:', e);
            return null;
        }
    },

    isAuthenticated: () => {
        const user = AuthService.getUser();
        return user && user.exp * 1000 > Date.now();
    }
};

// ==================== API SERVICE ====================
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

// ==================== INITIALIZATION ====================
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

function initTheme() {
    const savedTheme = localStorage.getItem('sc_theme');
    // Default to light mode if no preference saved
    if (savedTheme === 'dark') {
        document.body.classList.remove('light-mode');
        updateThemeIcon(false);
    } else {
        document.body.classList.add('light-mode');
        updateThemeIcon(true);
    }
}

function updateThemeIcon(isLight) {
    const icon = document.getElementById('theme-icon');
    if (icon) {
        // Use SVG icons for sun/moon
        if (isLight) {
            icon.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
        } else {
            icon.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
        }
    }
}

function initUI() {
    // Set user info in header
    const userNameEl = document.getElementById('user-name-display');
    const userRoleEl = document.getElementById('user-role-display');
    const userAvatarEl = document.getElementById('user-avatar');
    const groupNameEl = document.getElementById('group-name-display');
    const sidebarJoinCode = document.getElementById('sidebar-join-code');

    if (userNameEl) userNameEl.textContent = STATE.user.user_name || 'User';
    if (userRoleEl) {
        userRoleEl.textContent = STATE.user.role;
        userRoleEl.style.color = STATE.user.role === 'MANAGER' ? 'var(--accent-info)' : 'var(--accent-success)';
    }
    if (userAvatarEl) {
        userAvatarEl.textContent = (STATE.user.user_name || 'U').charAt(0).toUpperCase();
    }
    if (groupNameEl) groupNameEl.textContent = STATE.user.group_name || 'My Group';
    if (sidebarJoinCode) sidebarJoinCode.textContent = STATE.user.join_code || '------';

    // Manager-specific UI
    if (STATE.user.role === 'MANAGER') {
        const clearBtn = document.getElementById('clear-all-btn');
        const membersSection = document.getElementById('members-section');
        const formTitle = document.getElementById('form-title');
        const submitBtn = document.getElementById('submit-btn');

        if (clearBtn) clearBtn.style.display = 'flex';
        if (membersSection) membersSection.style.display = 'block';
        if (formTitle) formTitle.textContent = 'Add New Item';
        if (submitBtn) submitBtn.textContent = 'Add Item';
    } else {
        const formTitle = document.getElementById('form-title');
        const submitBtn = document.getElementById('submit-btn');

        if (formTitle) formTitle.textContent = 'Request Item';
        if (submitBtn) submitBtn.textContent = 'Submit Request';
    }
}

function setupEventListeners() {
    // Sidebar toggle
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    const sidebarClose = document.getElementById('sidebar-close');

    const openSidebar = () => {
        sidebar?.classList.add('open');
        sidebarOverlay?.classList.add('active');
        document.body.style.overflow = 'hidden';
    };

    const closeSidebar = () => {
        sidebar?.classList.remove('open');
        sidebarOverlay?.classList.remove('active');
        document.body.style.overflow = '';
    };

    menuToggle?.addEventListener('click', openSidebar);
    sidebarClose?.addEventListener('click', closeSidebar);
    sidebarOverlay?.addEventListener('click', closeSidebar);

    // Copy join code
    const copyCodeCard = document.getElementById('copy-code-card');
    copyCodeCard?.addEventListener('click', () => {
        const code = STATE.user.join_code;
        if (code) {
            navigator.clipboard.writeText(code);
            alert(`Invite code "${code}" copied to clipboard!`);
        }
    });

    // Logout
    const logoutBtn = document.getElementById('logout-btn');
    logoutBtn?.addEventListener('click', () => {
        if (confirm('Are you sure you want to sign out?')) {
            AuthService.logout();
        }
    });

    // Form submission
    const itemForm = document.getElementById('item-form');
    itemForm?.addEventListener('submit', handleFormSubmit);

    // Clear all
    const clearAllBtn = document.getElementById('clear-all-btn');
    clearAllBtn?.addEventListener('click', deleteAllItems);

    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    themeToggle?.addEventListener('click', () => {
        const isLight = document.body.classList.toggle('light-mode');
        localStorage.setItem('sc_theme', isLight ? 'light' : 'dark');
        updateThemeIcon(isLight);
    });
}

// ==================== DATA FETCHING ====================
async function fetchItems() {
    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/items`, { cache: 'no-store' });
        if (!response.ok) return;

        const items = await response.json();
        const hash = JSON.stringify(items);

        if (hash !== STATE.lastItemsHash) {
            STATE.items = items;
            STATE.lastItemsHash = hash;
            renderItems();
            updateStats();
        }
    } catch (err) {
        console.error('Error fetching items:', err);
    }
}

async function fetchMembers(forceRefresh = false) {
    if (STATE.user.role !== 'MANAGER') return;

    try {
        // Add cache-busting timestamp to ensure fresh data
        const url = forceRefresh
            ? `${CONFIG.API_BASE}/groups/members?t=${Date.now()}`
            : `${CONFIG.API_BASE}/groups/members`;
        const response = await secureFetch(url, { cache: 'no-store' });
        if (!response.ok) return;

        const members = await response.json();
        STATE.members = members;
        STATE.lastMembersHash = JSON.stringify(members);
        renderMembers();
    } catch (err) {
        console.error('Error fetching members:', err);
    }

}

async function syncUserIdentity() {
    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/auth/me`, { cache: 'no-store' });
        if (!response.ok) return;

        const freshUser = await response.json();

        // Critical: Detect Role Change
        if (freshUser.role !== STATE.user.role) {
            console.log(`Role changed from ${STATE.user.role} to ${freshUser.role}. Updating UI...`);
            STATE.user = { ...STATE.user, ...freshUser };

            // Full UI reset to update sidebar, buttons, and sections
            initUI();

            // Force re-check of pending section visibility with fresh role AND count
            const pendingCount = STATE.items.filter(i => i.status === 'PENDING').length;
            const container = document.getElementById('pending-section');
            if (container) {
                container.style.display = (freshUser.role === 'MANAGER' && pendingCount > 0) ? 'block' : 'none';
            }

            // Single render call after all UI state is updated
            renderItems();

            // If we gained Manager access, fetch members immediately
            if (freshUser.role === 'MANAGER') fetchMembers(true);
        } else {
            // Just update basic details
            STATE.user = { ...STATE.user, ...freshUser };
        }
    } catch (err) {
        console.error('Error syncing identity:', err);
    }
}


// ==================== ITEM OPERATIONS ====================
async function handleFormSubmit(e) {
    e.preventDefault();

    const nameInput = document.getElementById('name');
    const categoryInput = document.getElementById('category');
    const quantityInput = document.getElementById('quantity');

    const payload = {
        name: nameInput.value.trim(),
        category: categoryInput.value,
        quantity: parseInt(quantityInput.value) || 1
    };

    if (!payload.name) return;

    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/items`, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            nameInput.value = '';
            quantityInput.value = '1';
            fetchItems();
        }
    } catch (err) {
        console.error('Error adding item:', err);
    }
}

async function updateItemStatus(itemId, newStatus) {
    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/items/${itemId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: newStatus })
        });
        if (response.ok) fetchItems();
    } catch (err) {
        console.error('Error updating status:', err);
    }
}

async function updateQuantity(itemId, currentQty, delta) {
    const newQty = currentQty + delta;
    if (newQty < 1) return;

    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/items/${itemId}`, {
            method: 'PUT',
            body: JSON.stringify({ quantity: newQty })
        });
        if (response.ok) fetchItems();
    } catch (err) {
        console.error('Error updating quantity:', err);
    }
}

async function deleteItem(itemId) {
    if (!confirm('Delete this item?')) return;

    // Optimistic UI update: Remove item immediately
    const originalItems = [...STATE.items];
    STATE.items = STATE.items.filter(i => i._id !== itemId);
    renderItems(); // Re-render immediately so user sees it gone

    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/items/${itemId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            // Ignore 404s (already deleted), only alert on real errors
            if (response.status === 404) {
                console.warn('Item already deleted on server');
                fetchItems(); // Sync just in case
                return;
            }

            // Revert on failure
            STATE.items = originalItems;
            renderItems();
            alert('Failed to delete item.');
        } else {
            // Confirm with server state
            fetchItems();
        }
    } catch (err) {
        console.error('Error deleting item:', err);
        // Revert on error
        STATE.items = originalItems;
        renderItems();
    }
}

async function deleteAllItems() {
    if (!confirm('Clear the entire shopping list? This cannot be undone.')) return;

    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/items/clear`, {
            method: 'DELETE'
        });
        if (response.ok) fetchItems();
    } catch (err) {
        console.error('Error clearing items:', err);
    }
}

// ==================== MEMBER OPERATIONS ====================
async function promoteMember(userId) {
    if (!confirm('Promote this member to Manager?')) return;

    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/groups/members/${userId}`, {
            method: 'PUT',
            body: JSON.stringify({ role: 'MANAGER' })
        });
        console.log('Promote response:', response.status, response.ok);
        if (response.ok) {
            // Force full reload to update all permissions/UI
            window.location.reload();
        } else {
            const err = await response.json();
            console.error('Promote failed:', err);
            alert('Failed to promote member: ' + (err.error || 'Unknown error'));
        }
    } catch (err) {
        console.error('Error promoting member:', err);
    }
}

async function removeMember(userId) {
    if (!confirm('Remove this member from the group? Their account will be deleted.')) return;

    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/groups/members/${userId}`, {
            method: 'DELETE'
        });
        if (response.ok) fetchMembers();
    } catch (err) {
        console.error('Error removing member:', err);
    }
}

async function demoteMember(userId) {
    if (!confirm('Demote this manager to regular member?')) return;

    try {
        const response = await secureFetch(`${CONFIG.API_BASE}/groups/members/${userId}`, {
            method: 'PUT',
            body: JSON.stringify({ role: 'MEMBER' })
        });
        console.log('Demote response:', response.status, response.ok);
        if (response.ok) {
            // Force full reload to update all permissions/UI
            window.location.reload();
        } else {
            const err = await response.json();
            console.error('Demote failed:', err);
            alert('Failed to demote member: ' + (err.error || 'Unknown error'));
        }
    } catch (err) {
        console.error('Error demoting member:', err);
    }
}

// ==================== RENDERING ====================
function renderItems() {
    const container = document.getElementById('items-container');
    const pendingContainer = document.getElementById('pending-container');
    const myItemsContainer = document.getElementById('my-items-container');
    const myItemsSection = document.getElementById('my-items-section');
    if (!container) return;

    // Separate items by status
    const approvedItems = STATE.items.filter(i => i.status === 'APPROVED');
    const pendingItems = STATE.items.filter(i => i.status === 'PENDING');
    const rejectedItems = STATE.items.filter(i => i.status === 'REJECTED');

    // For regular users: show their own pending/rejected items
    if (STATE.user.role !== 'MANAGER' && myItemsContainer && myItemsSection) {
        const myItems = STATE.items.filter(i =>
            i.submitted_by === STATE.user.user_id &&
            (i.status === 'PENDING' || i.status === 'REJECTED')
        );

        if (myItems.length > 0) {
            myItemsSection.style.display = 'block';
            myItemsContainer.innerHTML = myItems.map((item, index) => renderItemCard(item, index, false, true)).join('');
        } else {
            myItemsSection.style.display = 'none';
        }
    }

    // Render pending items (for managers)
    if (pendingContainer && STATE.user.role === 'MANAGER') {
        if (pendingItems.length === 0) {
            pendingContainer.innerHTML = '<p class="text-muted" style="padding: 1rem;">No pending requests.</p>';
        } else {
            pendingContainer.innerHTML = pendingItems.map((item, index) => renderItemCard(item, index, true, false)).join('');
        }
    }

    // Render main shopping list (approved only for regular users, approved + rejected for managers)
    const mainListItems = STATE.user.role === 'MANAGER' ? [...approvedItems, ...rejectedItems] : approvedItems;

    if (mainListItems.length === 0) {
        container.innerHTML = `
            <div class="empty-state fade-in">
                <div class="empty-state-icon">&#128722;</div>
                <p class="empty-state-text">No items yet. Add your first item!</p>
            </div>
        `;
        return;
    }

    container.innerHTML = mainListItems.map((item, index) => renderItemCard(item, index, false, false)).join('');
}

function renderItemCard(item, index, isPending, isMyItem = false) {
    const totalPrice = ((item.price_nis || 0) * (item.quantity || 1)).toFixed(2);
    const isCalculating = item.ai_status === 'CALCULATING';
    const isError = item.ai_status === 'ERROR';

    // Always show status pill for my items, or when not pending
    const showStatus = isMyItem || !isPending;

    // Helper to format name nicely
    let submitterName = escapeHtml(item.submitted_by_name || 'Group Member');
    // If it looks like a raw ObjectID (hex string of 24 chars), fallback to generic name
    if (/^[0-9a-fA-F]{24}$/.test(submitterName)) {
        submitterName = 'Group Member';
    }

    return `
        <div class="item-card fade-in" style="animation-delay: ${index * 0.05}s">
            <div class="item-header">
                <div>
                    <div class="item-title">${escapeHtml(item.name)}</div>
                    <div class="item-submitter">by ${submitterName}</div>
                </div>
                ${showStatus ? `<span class="status-pill status-${item.status}">${item.status}</span>` : ''}
            </div>
            <div class="item-footer">
                <div class="item-meta">
                    <span class="meta-tag">${item.category || 'OTHER'}</span>
                    <div class="quantity-control">
                        <button class="quantity-btn" onclick="updateQuantity('${item._id}', ${item.quantity || 1}, -1)">-</button>
                        <span class="quantity-value">${item.quantity || 1}</span>
                        <button class="quantity-btn" onclick="updateQuantity('${item._id}', ${item.quantity || 1}, 1)">+</button>
                    </div>
                    ${isCalculating ? '<span class="text-muted">Calculating...</span>' :
            isError ? '<span class="price-error">Price unavailable</span>' :
                `<span class="price-tag">${totalPrice} NIS</span>`}
                </div>
                ${STATE.user.role === 'MANAGER' ? `
                    <div class="item-actions">
                        ${isPending ? `
                            <button class="btn btn-success btn-sm" onclick="updateItemStatus('${item._id}', 'APPROVED')">Approve</button>
                            <button class="btn btn-danger btn-sm" onclick="updateItemStatus('${item._id}', 'REJECTED')">Reject</button>
                        ` : ''}
                        <button class="btn btn-ghost btn-sm" onclick="deleteItem('${item._id}')">Delete</button>
                    </div>
                ` : (isMyItem && item.status === 'REJECTED') ? `
                    <div class="item-actions">
                        <button class="btn btn-ghost btn-sm" onclick="deleteItem('${item._id}')">Remove</button>
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}


function renderMembers() {
    const container = document.getElementById('members-list');
    if (!container) return;

    if (STATE.members.length === 0) {
        container.innerHTML = '<p class="text-muted" style="padding: 0.5rem;">No members found.</p>';
        return;
    }

    container.innerHTML = STATE.members.map(member => {
        const isCurrentUser = member.id === STATE.user.user_id;
        const isManager = member.role === 'MANAGER';

        return `
            <div class="member-card">
                <div class="member-info">
                    <div class="member-name">${escapeHtml(member.user_name || 'Unknown')}</div>
                    <div class="member-meta">${escapeHtml(member.email)} | ${member.role}</div>
                </div>
                ${!isCurrentUser ? `
                    <div class="member-actions">
                        ${!isManager ? `
                            <button class="btn btn-sm btn-ghost" onclick="promoteMember('${member.id}')">Promote</button>
                        ` : `
                            <button class="btn btn-sm btn-ghost" onclick="demoteMember('${member.id}')">Demote</button>
                        `}
                        <button class="btn btn-sm btn-danger" onclick="removeMember('${member.id}')">Remove</button>
                    </div>
                ` : '<span class="text-muted" style="font-size: 0.7rem;">You</span>'}
            </div>
        `;
    }).join('');
}



function updateStats() {
    // Only count APPROVED items in the cart total
    const total = STATE.items.reduce((sum, item) => {
        if (item.status === 'APPROVED') {
            return sum + ((item.price_nis || 0) * (item.quantity || 1));
        }
        return sum;
    }, 0);

    const approvedCount = STATE.items.filter(i => i.status === 'APPROVED').length;
    const pendingCount = STATE.items.filter(i => i.status === 'PENDING').length;

    const totalEl = document.getElementById('cart-total');
    const approvedEl = document.getElementById('approved-count');
    const pendingEl = document.getElementById('pending-count');

    if (totalEl) totalEl.textContent = total.toFixed(2) + ' NIS';
    if (approvedEl) approvedEl.textContent = approvedCount;
    if (pendingEl) pendingEl.textContent = pendingCount;

    // Show/hide pending section based on role and pending count
    const pendingSection = document.getElementById('pending-section');
    if (pendingSection) {
        pendingSection.style.display = (STATE.user.role === 'MANAGER' && pendingCount > 0) ? 'block' : 'none';
    }
}

// ==================== UTILITIES ====================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function startPolling() {
    // Initial fetch
    fetchItems();
    fetchMembers();
    syncUserIdentity();

    setInterval(() => {
        if (document.hidden) return; // Don't poll if tab is backgrounded
        fetchItems();
        fetchMembers();
        syncUserIdentity();
    }, CONFIG.POLLING_INTERVAL);
}