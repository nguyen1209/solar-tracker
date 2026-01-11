// Global variables
let users = [];

// Lấy user_id từ data attribute
const userDataElement = document.getElementById('userData');
let currentUserId = userDataElement ? parseInt(userDataElement.dataset.userId) || 0 : 0;

// Debug: Kiểm tra giá trị
console.log('User data element:', userDataElement);
console.log('Current user ID:', currentUserId);

// Show toast notification
function showToast(type, title, message, duration = 5000) {
    const toast = document.getElementById('toast');
    const toastTitle = document.getElementById('toastTitle');
    const toastMessage = document.getElementById('toastMessage');
    
    toastTitle.textContent = title;
    toastMessage.textContent = message;
    toast.className = `toast toast-${type}`;
    toast.style.display = 'flex';
    
    setTimeout(() => {
        toast.style.display = 'none';
    }, duration);
}

// Load users data
async function loadUsers() {
    try {
        showLoading(true);
        const response = await fetch('/api/users', {
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            if (response.status === 403) {
                showToast('error', 'Lỗi quyền truy cập', 'Bạn không có quyền xem danh sách người dùng!');
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        users = await response.json();
        renderUsersTable();
        loadActivityLog();
    } catch (error) {
        console.error('Error loading users:', error);
        showToast('error', 'Lỗi', 'Không thể tải danh sách người dùng: ' + error.message);
        showEmptyState();
    } finally {
        showLoading(false);
    }
}

function showLoading(show) {
    const usersLoading = document.getElementById('usersLoading');
    const usersTable = document.getElementById('usersTable');
    const emptyUsers = document.getElementById('emptyUsers');
    
    if (show) {
        usersLoading.style.display = 'block';
        usersTable.style.display = 'none';
        emptyUsers.style.display = 'none';
    } else {
        usersLoading.style.display = 'none';
    }
}

function showEmptyState() {
    const emptyUsers = document.getElementById('emptyUsers');
    const usersTable = document.getElementById('usersTable');
    const usersLoading = document.getElementById('usersLoading');
    
    usersLoading.style.display = 'none';
    emptyUsers.style.display = 'block';
    usersTable.style.display = 'none';
}

// Render users table
function renderUsersTable() {
    const usersTable = document.getElementById('usersTable');
    const usersTableBody = document.getElementById('usersTableBody');
    const emptyUsers = document.getElementById('emptyUsers');
    
    if (!users || users.length === 0) {
        showEmptyState();
        return;
    }
    
    emptyUsers.style.display = 'none';
    usersTable.style.display = 'table';
    
    usersTableBody.innerHTML = '';
    
    users.forEach(user => {
        const row = document.createElement('tr');
        
        // Format dates
        const createdDate = user.created_at ? 
            new Date(user.created_at).toLocaleDateString('vi-VN') : '--';
        const lastLogin = user.last_login ? 
            new Date(user.last_login).toLocaleString('vi-VN') : 'Chưa đăng nhập';
        
        // Get role badge class
        const roleClass = `role-${user.role || 'guest'}`;
        const roleDisplay = (user.role || 'guest').toUpperCase();
        
        row.innerHTML = `
            <td>${user.id || '--'}</td>
            <td><strong>${user.username || '--'}</strong></td>
            <td>${user.full_name || '--'}</td>
            <td><span class="role-badge ${roleClass}">${roleDisplay}</span></td>
            <td>${user.email || '--'}</td>
            <td>${createdDate}</td>
            <td>${lastLogin}</td>
            <td>
                <div class="action-buttons-cell">
                    <button class="action-btn edit-btn" onclick="openEditUserModal(${user.id})">
                        <i class="fas fa-edit"></i> Sửa
                    </button>
                    ${user.id !== currentUserId ? `
                    <button class="action-btn delete-btn" onclick="deleteUser(${user.id}, '${user.username}')">
                        <i class="fas fa-trash"></i> Xóa
                    </button>
                    ` : ''}
                </div>
            </td>
        `;
        
        usersTableBody.appendChild(row);
    });
}

// Load activity log
async function loadActivityLog() {
    try {
        const response = await fetch('/api/users/activity?limit=10', {
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            console.warn('Failed to fetch activity log, status:', response.status);
            return;
        }
        
        const activities = await response.json();
        const activityList = document.getElementById('activityList');
        const activityLog = document.getElementById('activityLog');
        
        if (!activities || activities.length === 0) {
            activityLog.style.display = 'none';
            return;
        }
        
        activityLog.style.display = 'block';
        activityList.innerHTML = '';
        
        activities.forEach(activity => {
            const item = document.createElement('div');
            item.className = 'activity-item';
            item.innerHTML = `
                <div><strong>${activity.username || 'Unknown'}</strong> - ${activity.description || 'No description'}</div>
                <div class="activity-time">
                    ${activity.timestamp || '--'} - ${activity.ip_address || '--'}
                </div>
            `;
            activityList.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading activity log:', error);
        document.getElementById('activityLog').style.display = 'none';
    }
}

// Create User Modal Functions
function openCreateUserModal() {
    document.getElementById('createUserModal').style.display = 'flex';
    document.getElementById('createUserForm').reset();
}

function closeCreateUserModal() {
    document.getElementById('createUserModal').style.display = 'none';
}

// Edit User Modal Functions
function openEditUserModal(userId) {
    const user = users.find(u => u.id === userId);
    if (!user) {
        showToast('error', 'Lỗi', 'Không tìm thấy người dùng!');
        return;
    }
    
    console.log("DEBUG openEditUserModal:", user);
    document.getElementById('editUserId').value = user.id;
    document.getElementById('editUsername').value = user.username || '';
    document.getElementById('editFullName').value = user.full_name || '';
    document.getElementById('editEmail').value = user.email || '';
    document.getElementById('editRole').value = user.role || 'viewer';

    document.getElementById('editUserModal').style.display = 'flex';
}

function closeEditUserModal() {
    document.getElementById('editUserModal').style.display = 'none';
}

// Form submission handlers
document.getElementById('createUserForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    
    // Validate password match
    if (data.password !== data.confirm_password) {
        showToast('error', 'Lỗi', 'Mật khẩu xác nhận không khớp');
        return;
    }
    
    try {
        const response = await fetch('/api/users', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showToast('success', 'Thành công', result.message);
            closeCreateUserModal();
            await loadUsers(); // Reload users
        } else {
            showToast('error', 'Lỗi', result.message || 'Không thể tạo người dùng');
        }
    } catch (error) {
        console.error('Error creating user:', error);
        showToast('error', 'Lỗi', 'Không thể kết nối đến server: ' + error.message);
    }
});

document.getElementById('editUserForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    const userId = data.user_id;
    
    try {
        const response = await fetch(`/api/users/${userId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showToast('success', 'Thành công', result.message);
            closeEditUserModal();
            await loadUsers(); // Reload users
        } else {
            showToast('error', 'Lỗi', result.message || 'Không thể cập nhật người dùng');
        }
    } catch (error) {
        console.error('Error updating user:', error);
        showToast('error', 'Lỗi', 'Không thể kết nối đến server: ' + error.message);
    }
});

// Delete user
async function deleteUser(userId, username) {
    if (!confirm(`Bạn có chắc chắn muốn xóa người dùng "${username}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/users/${userId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showToast('success', 'Thành công', result.message);
            await loadUsers(); // Reload users
        } else {
            showToast('error', 'Lỗi', result.message || 'Không thể xóa người dùng');
        }
    } catch (error) {
        console.error('Error deleting user:', error);
        showToast('error', 'Lỗi', 'Không thể kết nối đến server: ' + error.message);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadUsers();
    
    // Close modals when clicking outside
    window.addEventListener('click', (e) => {
        const createModal = document.getElementById('createUserModal');
        const editModal = document.getElementById('editUserModal');
        
        if (e.target === createModal) {
            closeCreateUserModal();
        }
        if (e.target === editModal) {
            closeEditUserModal();
        }
    });
});