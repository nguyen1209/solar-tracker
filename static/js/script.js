document.addEventListener('DOMContentLoaded', function() {
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm_password');
    const strengthFill = document.getElementById('strengthFill');
    const strengthText = document.getElementById('strengthText');
    const passwordMatch = document.getElementById('passwordMatch');
    const registerForm = document.getElementById('registerForm');
    
    // Check password strength
    function checkPasswordStrength(password) {
        let strength = 0;
        
        if (password.length >= 6) strength += 1;
        if (password.length >= 8) strength += 1;
        if (/[A-Z]/.test(password)) strength += 1;
        if (/[0-9]/.test(password)) strength += 1;
        if (/[^A-Za-z0-9]/.test(password)) strength += 1;
        
        return strength;
    }
    
    function updatePasswordStrength() {
        const password = passwordInput.value;
        const strength = checkPasswordStrength(password);
        
        let width = 0;
        let text = 'Yếu';
        let color = '#f56565';
        
        if (strength <= 1) {
            width = 25;
            text = 'Yếu';
            color = '#f56565';
        } else if (strength <= 3) {
            width = 50;
            text = 'Trung bình';
            color = '#ed8936';
        } else if (strength <= 4) {
            width = 75;
            text = 'Mạnh';
            color = '#48bb78';
        } else {
            width = 100;
            text = 'Rất mạnh';
            color = '#38a169';
        }
        
        strengthFill.style.width = width + '%';
        strengthFill.style.background = color;
        strengthText.textContent = text;
        strengthText.style.color = color;
    }
    
    function checkPasswordMatch() {
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        
        if (confirmPassword.length === 0) {
            passwordMatch.textContent = '';
            passwordMatch.style.color = '';
            return;
        }
        
        if (password === confirmPassword) {
            passwordMatch.innerHTML = '<i class="fas fa-check-circle"></i> Mật khẩu trùng khớp';
            passwordMatch.style.color = '#38a169';
        } else {
            passwordMatch.innerHTML = '<i class="fas fa-times-circle"></i> Mật khẩu không khớp';
            passwordMatch.style.color = '#f56565';
        }
    }
    
    // Toggle password visibility
    function addPasswordToggle(inputId) {
        const input = document.getElementById(inputId);
        const toggle = document.createElement('span');
        toggle.innerHTML = '👁️';
        toggle.style.cssText = `
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            cursor: pointer;
            user-select: none;
            font-size: 18px;
        `;
        
        input.parentNode.style.position = 'relative';
        input.parentNode.appendChild(toggle);
        
        toggle.addEventListener('click', function() {
            const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
            input.setAttribute('type', type);
            this.innerHTML = type === 'password' ? '👁️' : '👁️‍🗨️';
        });
    }
    
    // Validate username
    function validateUsername(username) {
        const usernameRegex = /^[a-zA-Z0-9_]{6,20}$/;
        return usernameRegex.test(username);
    }
    
    // Form validation
    function validateForm() {
        const username = document.getElementById('username').value;
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        const fullName = document.getElementById('full_name').value;
        
        // Validate username
        if (!validateUsername(username)) {
            alert('Tên đăng nhập phải có 6-20 ký tự và chỉ chứa chữ cái, số và gạch dưới!');
            return false;
        }
        
        // Validate full name
        if (fullName.trim().length === 0) {
            alert('Vui lòng nhập họ và tên!');
            return false;
        }
        
        // Validate password
        if (password.length < 6) {
            alert('Mật khẩu phải có ít nhất 6 ký tự!');
            return false;
        }
        
        // Check password match
        if (password !== confirmPassword) {
            alert('Mật khẩu xác nhận không khớp! Vui lòng kiểm tra lại.');
            return false;
        }
        
        return true;
    }
    
    // Event listeners
    passwordInput.addEventListener('input', updatePasswordStrength);
    passwordInput.addEventListener('input', checkPasswordMatch);
    confirmPasswordInput.addEventListener('input', checkPasswordMatch);
    
    // Add password toggles
    addPasswordToggle('password');
    addPasswordToggle('confirm_password');
    
    // Auto-focus username field
    document.getElementById('username').focus();
    
    // Form submission
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            if (!validateForm()) {
                e.preventDefault();
            }
        });
    }
    
    // Real-time username validation
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
        usernameInput.addEventListener('input', function() {
            const username = usernameInput.value;
            const feedback = document.getElementById('usernameFeedback') || 
                            (function() {
                                const div = document.createElement('div');
                                div.id = 'usernameFeedback';
                                div.style.fontSize = '0.85em';
                                div.style.marginTop = '5px';
                                usernameInput.parentNode.appendChild(div);
                                return div;
                            })();
            
            if (username.length === 0) {
                feedback.textContent = '';
                feedback.style.color = '';
            } else if (!validateUsername(username)) {
                feedback.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Tên đăng nhập phải có 6-20 ký tự (chữ, số, gạch dưới)';
                feedback.style.color = '#f56565';
            } else {
                feedback.innerHTML = '<i class="fas fa-check-circle"></i> Tên đăng nhập hợp lệ';
                feedback.style.color = '#38a169';
            }
        });
    }
    
    // Real-time full name validation
    const fullNameInput = document.getElementById('full_name');
    if (fullNameInput) {
        fullNameInput.addEventListener('input', function() {
            const fullName = fullNameInput.value.trim();
            const feedback = document.getElementById('fullNameFeedback') || 
                            (function() {
                                const div = document.createElement('div');
                                div.id = 'fullNameFeedback';
                                div.style.fontSize = '0.85em';
                                div.style.marginTop = '5px';
                                fullNameInput.parentNode.appendChild(div);
                                return div;
                            })();
            
            if (fullName.length === 0) {
                feedback.textContent = '';
                feedback.style.color = '';
            } else if (fullName.length < 2) {
                feedback.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Họ tên quá ngắn';
                feedback.style.color = '#f56565';
            } else {
                feedback.innerHTML = '<i class="fas fa-check-circle"></i> Hợp lệ';
                feedback.style.color = '#38a169';
            }
        });
    }
});