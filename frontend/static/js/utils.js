/**
 * 公共工具函数
 * Token 管理、LocalStorage 操作等
 */

const Utils = {
    /**
     * 保存 token 到 localStorage
     */
    saveToken(token) {
        localStorage.setItem('mailmerge_token', token);
    },

    /**
     * 获取 token
     */
    getToken() {
        return localStorage.getItem('mailmerge_token');
    },

    /**
     * 删除 token
     */
    removeToken() {
        localStorage.removeItem('mailmerge_token');
    },

    /**
     * 保存用户信息
     */
    saveUser(user) {
        localStorage.setItem('mailmerge_user', JSON.stringify(user));
    },

    /**
     * 获取用户信息
     */
    getUser() {
        const userStr = localStorage.getItem('mailmerge_user');
        return userStr ? JSON.parse(userStr) : null;
    },

    /**
     * 删除用户信息
     */
    removeUser() {
        localStorage.removeItem('mailmerge_user');
    },

    /**
     * 清除所有认证信息
     */
    clearAuth() {
        this.removeToken();
        this.removeUser();
    },

    /**
     * 检查是否已登录
     */
    isAuthenticated() {
        return !!this.getToken();
    },

    /**
     * 获取带认证头的请求配置
     */
    getAuthHeaders() {
        const token = this.getToken();
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    },

    /**
     * 转义 HTML 特殊字符
     */
    escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    },

    /**
     * 格式化日期
     */
    formatDate(date) {
        if (!date) return '';
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    },

    /**
     * 格式化日期时间
     */
    formatDateTime(date) {
        if (!date) return '';
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hour = String(d.getHours()).padStart(2, '0');
        const minute = String(d.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day} ${hour}:${minute}`;
    },

    /**
     * 验证邮箱格式
     */
    validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },

    /**
     * 验证手机号格式
     */
    validatePhone(phone) {
        const re = /^1[3-9]\d{9}$/;
        return re.test(phone);
    },

    /**
     * 显示确认对话框
     */
    confirm(message) {
        return window.confirm(message);
    },

    /**
     * 显示提示消息
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型: 'success', 'error', 'warning', 'info'
     */
    showToast(message, type = 'info') {
        // 创建toast容器（如果不存在）
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                z-index: 10000;
                pointer-events: none;
            `;
            document.body.appendChild(toastContainer);
        }

        // 创建toast元素
        const toast = document.createElement('div');
        toast.style.cssText = `
            background: ${this.getToastColor(type)};
            color: white;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            font-size: 14px;
            max-width: 300px;
            word-wrap: break-word;
            pointer-events: auto;
            cursor: pointer;
            animation: toastSlideIn 0.3s ease-out;
        `;

        toast.textContent = message;
        toast.onclick = () => this.removeToast(toast);

        toastContainer.appendChild(toast);

        // 自动移除
        setTimeout(() => this.removeToast(toast), 5000);
    },

    /**
     * 获取toast颜色
     */
    getToastColor(type) {
        const colors = {
            success: '#10B981',
            error: '#EF4444',
            warning: '#F59E0B',
            info: '#3B82F6'
        };
        return colors[type] || colors.info;
    },

    /**
     * 移除toast
     */
    removeToast(toast) {
        toast.style.animation = 'toastSlideOut 0.3s ease-in';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }
};

// 全局导出
window.Utils = Utils;
