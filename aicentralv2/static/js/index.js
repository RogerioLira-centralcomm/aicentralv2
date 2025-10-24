/**
 * INDEX2 - JavaScript Minimalista
 */

'use strict';

document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Index2 carregado');
    
    initPills();
    initExpandRows();
    initSidebar();
});

// ==================== PILLS NAVIGATION ====================

function initPills() {
    const pills = document.querySelectorAll('.pill');
    
    pills.forEach(pill => {
        pill.addEventListener('click', function() {
            pills.forEach(p => p.classList.remove('active'));
            this.classList.add('active');
            
            const text = this.textContent.trim();
            console.log(`📍 Navegando para: ${text}`);
        });
    });
}

// ==================== EXPAND ROWS ====================

function initExpandRows() {
    const expandBtns = document.querySelectorAll('.expand-icon');
    
    expandBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            
            const icon = this.querySelector('i');
            
            if (icon.classList.contains('fa-chevron-down')) {
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-up');
                console.log('📂 Expandindo linha');
            } else {
                icon.classList.remove('fa-chevron-up');
                icon.classList.add('fa-chevron-down');
                console.log('📁 Recolhendo linha');
            }
        });
    });
}

// ==================== SIDEBAR ====================

function initSidebar() {
    const sidebarIcons = document.querySelectorAll('.sidebar-icon');
    
    sidebarIcons.forEach(icon => {
        icon.addEventListener('click', function() {
            console.log('🔘 Ícone da sidebar clicado');
        });
    });
}

// ==================== ACTION BUTTONS ====================

const actionButtons = document.querySelectorAll('.btn-action');

actionButtons.forEach(btn => {
    btn.addEventListener('click', function() {
        const text = this.textContent.trim();
        console.log(`🚀 Ação: ${text}`);
    });
});

// ==================== MOBILE MENU ====================

const menuBtn = document.querySelector('.menu-btn');

if (menuBtn) {
    menuBtn.addEventListener('click', function() {
        console.log('📱 Menu mobile');
    });
}

console.log('%c✨ Index2 Pronto', 'color: #6E56CF; font-weight: bold;');