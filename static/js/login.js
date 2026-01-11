document.addEventListener('DOMContentLoaded', function() {
    const passwordInput = document.getElementById('password');
    const loginForm = document.getElementById('loginForm');
    const demoAccounts = document.querySelectorAll('.demo-account');
    
    // Add password toggle functionality
    function addPasswordToggle() {
        const togglePassword = document.createElement('span');
        togglePassword.innerHTML = '👁️';
        togglePassword.className = 'password-toggle';
        
        passwordInput.parentNode.style.position = 'relative';
        passwordInput.parentNode.appendChild(togglePassword);
        
        togglePassword.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            this.innerHTML = type === 'password' ? '👁️' : '👁️‍🗨️';
        });
    }
    
    // Auto-fill demo account credentials
    function setupDemoAccounts() {
        demoAccounts.forEach(account => {
            account.addEventListener('click', function() {
                const credentialsText = this.querySelector('.credentials').textContent;
                const lines = credentialsText.split('\n');
                
                let username = '';
                let password = '';
                
                lines.forEach(line => {
                    if (line.toLowerCase().includes('user:')) {
                        username = line.split(':')[1].trim();
                    }
                    if (line.toLowerCase().includes('pass:')) {
                        password = line.split(':')[1].trim();
                    }
                });
                
                if (username && password) {
                    document.getElementById('username').value = username;
                    passwordInput.value = password;
                    
                    // Show confirmation
                    const role = this.querySelector('.role').textContent.split(' ')[0];
                    showNotification(`Đã điền thông tin cho tài khoản ${role}`, 'success');
                }
            });
        });
    }
    
    // Form validation
    function validateLoginForm() {
        const username = document.getElementById('username').value.trim();
        const password = passwordInput.value.trim();
        
        if (!username) {
            showNotification('Vui lòng nhập tên đăng nhập!', 'error');
            return false;
        }
        
        if (!password) {
            showNotification('Vui lòng nhập mật khẩu!', 'error');
            return false;
        }
        
        if (password.length < 6) {
            showNotification('Mật khẩu phải có ít nhất 6 ký tự!', 'error');
            return false;
        }
        
        return true;
    }
    
    // Show notification
    function showNotification(message, type) {
        // Remove existing notification
        const existingNotification = document.querySelector('.custom-notification');
        if (existingNotification) {
            existingNotification.remove();
        }
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `custom-notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            animation: slideIn 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        
        // Set background color based on type
        if (type === 'success') {
            notification.style.background = '#38a169';
        } else if (type === 'error') {
            notification.style.background = '#e53e3e';
        } else {
            notification.style.background = '#667eea';
        }
        
        // Add animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
        
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            notification.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
    
    // Add quick login buttons for demo accounts
    function addQuickLoginButtons() {
        const quickLoginContainer = document.createElement('div');
        quickLoginContainer.className = 'quick-login';
        
        const roles = ['Admin', 'Operator', 'Viewer', 'Guest'];
        roles.forEach(role => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'quick-login-btn';
            button.textContent = role;
            button.addEventListener('click', function() {
                let username = '';
                let password = '';
                
                switch(role) {
                    case 'Admin':
                        username = 'admin';
                        password = 'admin123';
                        break;
                    case 'Operator':
                        username = 'operator';
                        password = 'operator123';
                        break;
                    case 'Viewer':
                        username = 'viewer';
                        password = 'viewer123';
                        break;
                    case 'Guest':
                        username = 'guest';
                        password = 'guest123';
                        break;
                }
                
                document.getElementById('username').value = username;
                passwordInput.value = password;
                showNotification(`Đã điền thông tin ${role}`, 'success');
            });
            
            quickLoginContainer.appendChild(button);
        });
        
        // Insert after the form
        const form = document.querySelector('form');
        if (form) {
            form.appendChild(quickLoginContainer);
        }
    }
    
    // Auto-focus username field
    document.getElementById('username').focus();
    
    // Form submission
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            if (!validateLoginForm()) {
                e.preventDefault();
            }
        });
    }
    
    // Add Enter key support
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && e.target.tagName !== 'BUTTON') {
            if (loginForm && validateLoginForm()) {
                // Form will submit normally
            }
        }
    });
    
    // Initialize all features
    addPasswordToggle();
    setupDemoAccounts();
    addQuickLoginButtons();
    
    // Add remember me functionality
    function setupRememberMe() {
        const rememberMeDiv = document.createElement('div');
        rememberMeDiv.className = 'form-group';
        rememberMeDiv.style.marginTop = '15px';
        
        const rememberMeLabel = document.createElement('label');
        rememberMeLabel.style.cursor = 'pointer';
        rememberMeLabel.style.display = 'flex';
        rememberMeLabel.style.alignItems = 'center';
        rememberMeLabel.style.fontSize = '0.9em';
        rememberMeLabel.style.color = '#4a5568';
        
        const rememberMeCheckbox = document.createElement('input');
        rememberMeCheckbox.type = 'checkbox';
        rememberMeCheckbox.id = 'rememberMe';
        rememberMeCheckbox.name = 'rememberMe';
        rememberMeCheckbox.style.marginRight = '8px';
        
        const rememberMeText = document.createTextNode(' Ghi nhớ đăng nhập');
        
        rememberMeLabel.appendChild(rememberMeCheckbox);
        rememberMeLabel.appendChild(rememberMeText);
        rememberMeDiv.appendChild(rememberMeLabel);
        
        // Insert before the submit button
        const submitButton = document.querySelector('.btn');
        if (submitButton) {
            submitButton.parentNode.insertBefore(rememberMeDiv, submitButton);
        }
        
        // Load saved credentials if available
        const savedUsername = localStorage.getItem('savedUsername');
        const savedPassword = localStorage.getItem('savedPassword');
        
        if (savedUsername && savedPassword) {
            document.getElementById('username').value = savedUsername;
            passwordInput.value = savedPassword;
            rememberMeCheckbox.checked = true;
        }
        
        // Update saved credentials on form submit
        if (loginForm) {
            loginForm.addEventListener('submit', function() {
                if (rememberMeCheckbox.checked) {
                    localStorage.setItem('savedUsername', document.getElementById('username').value);
                    localStorage.setItem('savedPassword', passwordInput.value);
                } else {
                    localStorage.removeItem('savedUsername');
                    localStorage.removeItem('savedPassword');
                }
            });
        }
    }
    
    // Initialize remember me feature
    setupRememberMe();
});