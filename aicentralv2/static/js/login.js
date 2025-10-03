// Inspirational quotes from great entrepreneurs
const inspirationalQuotes = [
    {
        text: "A inovação distingue um líder de um seguidor.",
        author: "Steve Jobs"
    },
    {
        text: "O sucesso é ir de fracasso em fracasso sem perder o entusiasmo.",
        author: "Winston Churchill"
    },
    {
        text: "Sua única limitação é você mesmo.",
        author: "Henry Ford"
    },
    {
        text: "O futuro pertence àqueles que acreditam na beleza de seus sonhos.",
        author: "Eleanor Roosevelt"
    },
    {
        text: "A persistência é o caminho do êxito.",
        author: "Charles Chaplin"
    },
    {
        text: "Não tenha medo de desistir do bom para buscar o ótimo.",
        author: "John D. Rockefeller"
    },
    {
        text: "A comunicação eficaz é 20% do que você sabe e 80% de como você se sente sobre o que sabe.",
        author: "Jim Rohn"
    },
    {
        text: "O segredo da mudança é focar toda sua energia não em lutar contra o velho, mas em construir o novo.",
        author: "Sócrates"
    }
];

// Background images for hero section
const backgroundImages = [
    'https://images.unsplash.com/photo-1451187580459-43490279c0fa?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80',
    'https://images.unsplash.com/photo-1518837695005-2083093ee35b?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80',
    'https://images.unsplash.com/photo-1462332420958-a05d1e002413?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80',
    'https://images.unsplash.com/photo-1446776877081-d282a0f896e2?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80',
    'https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80',
    'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80'
];

let currentQuoteIndex = 0;
let currentBackgroundIndex = 0;

document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const loadingOverlay = document.getElementById('loadingOverlay');

    // Initialize hero section
    initializeHeroSection();
    
    // Load saved email if remember me was checked
    loadSavedCredentials();

    // Form submission handler
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(loginForm);
        const loginData = {
            email: formData.get('email'),
            password: formData.get('password'),
            remember: formData.get('remember') === 'on'
        };

        // Basic validation
        if (!validateForm(loginData)) {
            return;
        }

        try {
            showLoading(true);
            
            // Simulate API call
            await simulateLogin(loginData);
            
            // Save credentials if remember me is checked
            if (loginData.remember) {
                saveCredentials(loginData.email);
            } else {
                clearSavedCredentials();
            }
            
            // Redirect to dashboard
            showSuccess('Acesso autorizado! Redirecionando...');
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, 1500);
            
        } catch (error) {
            showError(error.message);
        } finally {
            showLoading(false);
        }
    });

    // Animate form elements on load
    animateFormElements();
});

function initializeHeroSection() {
    // Set initial background
    changeBackground();
    
    // Set initial quote
    changeQuote();
    
    // Animate features
    setTimeout(() => {
        const features = document.querySelectorAll('.feature');
        features.forEach((feature, index) => {
            setTimeout(() => {
                feature.classList.add('animate');
            }, index * 200);
        });
    }, 1000);
    
    // Change background every 10 seconds
    setInterval(changeBackground, 10000);
    
    // Change quote every 8 seconds
    setInterval(changeQuote, 8000);
}

function changeBackground() {
    const heroBackground = document.getElementById('heroBackground');
    const newImage = backgroundImages[currentBackgroundIndex];
    
    heroBackground.style.backgroundImage = `url('${newImage}')`;
    currentBackgroundIndex = (currentBackgroundIndex + 1) % backgroundImages.length;
}

function changeQuote() {
    const quoteText = document.getElementById('quoteText');
    const quoteAuthor = document.getElementById('quoteAuthor');
    const currentQuote = inspirationalQuotes[currentQuoteIndex];
    
    // Fade out current quote
    quoteText.classList.remove('active');
    quoteAuthor.classList.remove('active');
    
    setTimeout(() => {
        // Change text
        quoteText.textContent = `"${currentQuote.text}"`;
        quoteAuthor.textContent = currentQuote.author;
        
        // Fade in new quote
        quoteText.classList.add('active');
        quoteAuthor.classList.add('active');
        
        currentQuoteIndex = (currentQuoteIndex + 1) % inspirationalQuotes.length;
    }, 400);
}

function animateFormElements() {
    const elements = document.querySelectorAll('.login-form-container > *');
    elements.forEach((element, index) => {
        element.style.opacity = '0';
        element.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            element.style.transition = 'all 0.6s ease';
            element.style.opacity = '1';
            element.style.transform = 'translateY(0)';
        }, index * 100 + 500);
    });
}

function togglePassword() {
    const passwordInput = document.getElementById('password');
    const toggleBtn = document.querySelector('.toggle-password i');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleBtn.classList.remove('fa-eye');
        toggleBtn.classList.add('fa-eye-slash');
    } else {
        passwordInput.type = 'password';
        toggleBtn.classList.remove('fa-eye-slash');
        toggleBtn.classList.add('fa-eye');
    }
}

function validateForm(data) {
    const { email, password } = data;
    
    // Email validation - check if it's a CentralComm email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showError('Por favor, insira um email corporativo válido.');
        return false;
    }
    
    // Password validation
    if (password.length < 6) {
        showError('A senha deve ter pelo menos 6 caracteres.');
        return false;
    }
    
    return true;
}

async function simulateLogin(data) {
    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Simulate authentication with CentralComm credentials
    const validEmails = [
        'admin@centralcomm.com',
        'suporte@centralcomm.com',
        'operador@centralcomm.com',
        'supervisor@centralcomm.com'
    ];
    
    if (validEmails.includes(data.email.toLowerCase()) && data.password === 'centralcomm2024') {
        return { success: true, user: { email: data.email, name: 'Usuário CentralComm' } };
    } else {
        throw new Error('Credenciais inválidas. Verifique email e senha corporativos.');
    }
}

function showLoading(show) {
    const loadingOverlay = document.getElementById('loadingOverlay');
    loadingOverlay.style.display = show ? 'flex' : 'none';
}

function showError(message) {
    showNotification(message, 'error');
}

function showSuccess(message) {
    showNotification(message, 'success');
}

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fas ${type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Add styles
    Object.assign(notification.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        padding: '1rem 1.5rem',
        borderRadius: '12px',
        color: 'white',
        fontWeight: '500',
        zIndex: '10000',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        minWidth: '300px',
        boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
        background: type === 'error' ? '#e74c3c' : '#27ae60',
        transform: 'translateX(400px)',
        transition: 'transform 0.3s ease',
        backdropFilter: 'blur(10px)'
    });
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);
    
    // Remove after delay
    setTimeout(() => {
        notification.style.transform = 'translateX(400px)';
        setTimeout(() => {
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 4000);
}

function saveCredentials(email) {
    localStorage.setItem('centralcommEmail', email);
    localStorage.setItem('centralcommRemember', 'true');
}

function loadSavedCredentials() {
    const rememberedEmail = localStorage.getItem('centralcommEmail');
    const rememberMe = localStorage.getItem('centralcommRemember') === 'true';
    
    if (rememberMe && rememberedEmail) {
        document.getElementById('email').value = rememberedEmail;
        document.getElementById('remember').checked = true;
    }
}

function clearSavedCredentials() {
    localStorage.removeItem('centralcommEmail');
    localStorage.removeItem('centralcommRemember');
}

function openWhatsAppSupport() {
    const phoneNumber = '5511999999999'; // Replace with actual IT support number
    const message = encodeURIComponent('Olá! Preciso de suporte técnico para acesso ao CentralComm Hub.');
    const whatsappUrl = `https://wa.me/${phoneNumber}?text=${message}`;
    
    window.open(whatsappUrl, '_blank');
}

// Social login handlers
document.addEventListener('DOMContentLoaded', function() {
    const googleBtn = document.querySelector('.social-btn.google');
    const microsoftBtn = document.querySelector('.social-btn.microsoft');
    
    if (googleBtn) {
        googleBtn.addEventListener('click', handleGoogleLogin);
    }
    
    if (microsoftBtn) {
        microsoftBtn.addEventListener('click', handleMicrosoftLogin);
    }
});

function handleGoogleLogin() {
    showNotification('Redirecionando para login do Google...', 'success');
    // Implement Google OAuth integration here
    setTimeout(() => {
        console.log('Google login would be implemented here');
    }, 1000);
}

function handleMicrosoftLogin() {
    showNotification('Redirecionando para login da Microsoft...', 'success');
    // Implement Microsoft OAuth integration here
    setTimeout(() => {
        console.log('Microsoft login would be implemented here');
    }, 1000);
}

// Add smooth scrolling and additional animations
window.addEventListener('load', function() {
    // Animate elements on load
    const elements = document.querySelectorAll('.login-form-container > *');
    elements.forEach((element, index) => {
        element.style.opacity = '0';
        element.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            element.style.transition = 'all 0.6s ease';
            element.style.opacity = '1';
            element.style.transform = 'translateY(0)';
        }, index * 100);
    });
});
