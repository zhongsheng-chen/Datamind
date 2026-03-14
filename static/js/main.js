// datamind/static/js/main.js

// 全局配置
const API_BASE = '/api/v1';

// 工具函数
const utils = {
    // 格式化日期
    formatDate: function(date) {
        return new Date(date).toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    // 显示提示消息
    showToast: function(message, type = 'success') {
        // 创建toast容器
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.style.position = 'fixed';
            toastContainer.style.top = '20px';
            toastContainer.style.right = '20px';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }

        // 创建toast
        const toastId = 'toast_' + Date.now();
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        toastContainer.appendChild(toast);

        // 初始化并显示
        const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
        bsToast.show();

        // 自动移除
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    },

    // 显示确认对话框
    confirm: function(message, title = '确认操作') {
        return new Promise((resolve) => {
            if (confirm(`${title}\n\n${message}`)) {
                resolve(true);
            } else {
                resolve(false);
            }
        });
    },

    // 处理API错误
    handleError: function(error) {
        console.error('API Error:', error);

        let message = '操作失败';
        if (error.response) {
            message = error.response.data?.detail || error.response.statusText || message;
        } else if (error.message) {
            message = error.message;
        }

        this.showToast(message, 'danger');
    },

    // 获取CSRF令牌
    getCsrfToken: function() {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    }
};

// API调用函数
const api = {
    // GET请求
    get: async function(url) {
        const response = await fetch(API_BASE + url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'demo-key'  // 开发环境使用，生产环境需要替换
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw { response: { data: error, status: response.status } };
        }

        return response.json();
    },

    // POST请求
    post: async function(url, data) {
        const response = await fetch(API_BASE + url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'demo-key'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            throw { response: { data: error, status: response.status } };
        }

        return response.json();
    },

    // 文件上传
    upload: async function(url, formData) {
        const response = await fetch(API_BASE + url, {
            method: 'POST',
            headers: {
                'X-API-Key': 'demo-key'
            },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw { response: { data: error, status: response.status } };
        }

        return response.json();
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化所有tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 初始化所有popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});