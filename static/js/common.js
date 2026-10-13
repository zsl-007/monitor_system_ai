// 通用JavaScript功能

// 显示消息提示
function showMessage(message, type = 'success') {
    const alertClass = type === 'success' ? 'alert-success' : 
                       type === 'error' ? 'alert-danger' : 
                       type === 'warning' ? 'alert-warning' : 'alert-info';
    
    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // 在页面顶部显示消息
    const container = document.querySelector('.container');
    if (container) {
        container.insertAdjacentHTML('afterbegin', alertHtml);
        
        // 5秒后自动消失
        setTimeout(() => {
            const alert = document.querySelector('.alert');
            if (alert) {
                alert.remove();
            }
        }, 5000);
    }
}

// 处理AJAX错误
function handleAjaxError(error) {
    console.error('AJAX Error:', error);
    showMessage('操作失败: ' + (error.message || '网络错误'), 'error');
}

// 格式化时间
function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN');
}

// 更新当前时间
function updateCurrentTime() {
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        const now = new Date();
        timeElement.textContent = now.toLocaleString('zh-CN');
    }
}

// 全局AJAX错误处理
function setupAjaxErrorHandling() {
    // 保存原始的fetch函数
    const originalFetch = window.fetch;
    
    // 重写fetch函数
    window.fetch = function(...args) {
        return originalFetch.apply(this, args)
            .then(response => {
                if (response.status === 401) {
                    // 未授权，跳转到登录页面
                    window.location.href = '/login';
                    return Promise.reject(new Error('未授权'));
                }
                return response;
            })
            .catch(error => {
                if (error.message.includes('未授权')) {
                    // 已经处理了跳转，不需要再次处理
                    return;
                }
                console.error('Fetch error:', error);
                throw error;
            });
    };
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    setupAjaxErrorHandling();// 页面加载完成后设置错误处理

    // 更新当前时间
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    
    // 初始化工具提示
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 处理所有删除按钮的确认
    document.querySelectorAll('.btn-danger, .delete-config').forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('确定要删除吗？此操作不可恢复。')) {
                e.preventDefault();
            }
        });
    });
});

// 统一的API请求函数
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            credentials: 'include',
            ...options
        });
        
        if (!response.ok) {
            // 如果是认证错误，跳转到登录页面
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }
            
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || errorData.detail || `HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API请求错误:', error);
        throw error;
    }
}