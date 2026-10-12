// 主JavaScript文件

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化工具提示
    initTooltips();
    
    // 初始化确认对话框
    initConfirmDialogs();
    
    // 初始化表单验证
    initFormValidation();
    
    // 初始化页面动画
    initAnimations();
    
    // 初始化懒加载
    initLazyLoading();
    
    // 初始化搜索功能
    initSearch();
    
    // 初始化无限滚动
    initInfiniteScroll();
    
    // 检查网络状态
    checkNetworkStatus();
    
    // 初始化通知系统
    // 通知系统已移除
});

// 初始化Bootstrap工具提示
function initTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// 初始化确认对话框
function initConfirmDialogs() {
    // 为删除按钮添加确认对话框
    document.querySelectorAll('[data-confirm]').forEach(function(element) {
        element.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm') || '确定要执行此操作吗？';
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });
}

// 初始化表单验证
function initFormValidation() {
    // Bootstrap表单验证
    var forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // 自定义验证规则
    addCustomValidations();
}

// 添加自定义验证规则
function addCustomValidations() {
    // 账号验证（6位以上）
    const accountInputs = document.querySelectorAll('input[name="account"]');
    accountInputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            if (this.value.length > 0 && this.value.length < 6) {
                this.setCustomValidity('账号必须至少6位');
                this.classList.add('is-invalid');
            } else {
                this.setCustomValidity('');
                this.classList.remove('is-invalid');
            }
        });
    });
    
    // 密码验证（6位以上）
    const passwordInputs = document.querySelectorAll('input[name="password"]');
    passwordInputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            if (this.value.length > 0 && this.value.length < 6) {
                this.setCustomValidity('密码必须至少6位');
                this.classList.add('is-invalid');
            } else {
                this.setCustomValidity('');
                this.classList.remove('is-invalid');
            }
        });
    });
    
    // 年龄验证
    const ageInputs = document.querySelectorAll('input[name="age"]');
    ageInputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            const age = parseInt(this.value);
            if (this.value && (age < 1 || age > 120)) {
                this.setCustomValidity('请输入有效的年龄（1-120）');
                this.classList.add('is-invalid');
            } else {
                this.setCustomValidity('');
                this.classList.remove('is-invalid');
            }
        });
    });
}

// 初始化页面动画
function initAnimations() {
    // 添加淡入动画
    const animatedElements = document.querySelectorAll('.fade-in-up');
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'fadeInUp 0.6s ease-out';
                observer.unobserve(entry.target);
            }
        });
    });
    
    animatedElements.forEach(function(element) {
        observer.observe(element);
    });
}

// 初始化懒加载
function initLazyLoading() {
    const images = document.querySelectorAll('img[data-src]');
    
    const imageObserver = new IntersectionObserver(function(entries, observer) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.getAttribute('data-src');
                img.removeAttribute('data-src');
                img.classList.add('loaded');
                observer.unobserve(img);
            }
        });
    });
    
    images.forEach(function(img) {
        imageObserver.observe(img);
    });
}

// 初始化搜索功能
function initSearch() {
    const searchInputs = document.querySelectorAll('.search-input');
    
    searchInputs.forEach(function(input) {
        let searchTimeout;
        
        input.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const searchTerm = this.value.trim();
            
            if (searchTerm.length >= 2) {
                searchTimeout = setTimeout(function() {
                    performSearch(searchTerm);
                }, 300);
            }
        });
    });
}

// 执行搜索
function performSearch(searchTerm) {
    // 实现搜索逻辑
    console.log('搜索:', searchTerm);
}

// 初始化无限滚动
function initInfiniteScroll() {
    const loadMoreButton = document.querySelector('.load-more');
    
    if (loadMoreButton) {
        window.addEventListener('scroll', function() {
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 1000) {
                loadMoreContent();
            }
        });
    }
}

// 加载更多内容
function loadMoreContent() {
    // 实现加载更多内容的逻辑
    console.log('加载更多内容...');
}

// 检查网络状态
function checkNetworkStatus() {
    function updateNetworkStatus() {
        if (navigator.onLine) {
            showMessage('网络已连接', 'success');
        } else {
            showMessage('网络连接已断开', 'danger');
        }
    }
    
    window.addEventListener('online', updateNetworkStatus);
    window.addEventListener('offline', updateNetworkStatus);
}

// 显示消息提示
function showMessage(message, type = 'info', duration = 3000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // 自动消失
    setTimeout(function() {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, duration);
}

// 显示加载状态
function showLoading(element, show = true) {
    if (show) {
        element.disabled = true;
        const originalText = element.textContent;
        element.setAttribute('data-original-text', originalText);
        element.innerHTML = '<span class="loading"></span> 加载中...';
    } else {
        element.disabled = false;
        const originalText = element.getAttribute('data-original-text');
        if (originalText) {
            element.textContent = originalText;
            element.removeAttribute('data-original-text');
        }
    }
}

// Ajax请求封装
function ajaxRequest(url, options = {}) {
    const defaults = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    };
    
    const config = Object.assign({}, defaults, options);
    
    return fetch(url, config)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .catch(error => {
            console.error('Ajax请求失败:', error);
            showMessage('请求失败，请稍后重试', 'danger');
            throw error;
        });
}

// 格式化日期
function formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

// 数字格式化
function formatNumber(num, decimals = 0) {
    return num.toLocaleString('zh-CN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

// 防抖函数
function debounce(func, wait, immediate = false) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

// 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// 复制到剪贴板
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function() {
            showMessage('已复制到剪贴板', 'success');
        });
    } else {
        // 兼容老浏览器
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showMessage('已复制到剪贴板', 'success');
        } catch (err) {
            showMessage('复制失败', 'danger');
        }
        document.body.removeChild(textArea);
    }
}

// 获取URL参数
function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

// 设置URL参数
function setUrlParameter(name, value) {
    const url = new URL(window.location);
    url.searchParams.set(name, value);
    window.history.pushState({}, '', url);
}

// 平滑滚动到元素
function scrollToElement(element, offset = 0) {
    const elementPosition = element.offsetTop - offset;
    window.scrollTo({
        top: elementPosition,
        behavior: 'smooth'
    });
}

// 检测是否为移动设备
function isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// 全局错误处理
window.addEventListener('error', function(e) {
    console.error('全局错误:', e.error);
    showMessage('页面发生错误，请刷新页面重试', 'danger');
});

// 全局未处理的Promise拒绝
window.addEventListener('unhandledrejection', function(e) {
    console.error('未处理的Promise拒绝:', e.reason);
    showMessage('系统异常，请稍后重试', 'danger');
});

// 通知系统已移除

// 积分奖励动画
function showPointsRewardAnimation(points) {
    const animation = document.createElement('div');
    animation.className = 'points-reward-animation';
    animation.innerHTML = `
        <i class="fas fa-coins"></i>
        <span>+${points} 积分</span>
    `;
    
    document.body.appendChild(animation);
    
    // 动画效果
    setTimeout(() => {
        animation.classList.add('animate');
    }, 100);
    
    // 清理
    setTimeout(() => {
        animation.remove();
    }, 3000);
}

// 导出常用函数到全局
window.showMessage = showMessage;
window.showLoading = showLoading;
window.ajaxRequest = ajaxRequest;
window.formatDate = formatDate;
window.formatNumber = formatNumber;
window.copyToClipboard = copyToClipboard;
// 通知相关函数已移除
window.showPointsRewardAnimation = showPointsRewardAnimation;
