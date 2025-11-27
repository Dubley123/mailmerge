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
    }
};

// 全局导出
window.Utils = Utils;
