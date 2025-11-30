/**
 * 认证相关 API
 * 登录、注册、登出等
 */

const AuthAPI = {
    /**
     * 用户登录
     */
    async login(account, password) {
        const response = await CommonAPI.post('/api/auth/login', { account, password });
        
        if (response.success) {
            const { token, user } = response.data;
            Utils.saveToken(token);
            Utils.saveUser(user);  // 直接保存user对象，不是response.data
            return { success: true, user };
        } else {
            return { success: false, message: response.error || '登录失败' };
        }
    },

    /**
     * 用户注册
     */
    async register(formData) {
        const response = await CommonAPI.post('/api/auth/register', formData);
        return response.success 
            ? { success: true, message: '注册成功' }
            : { success: false, message: response.error || '注册失败' };
    },

    /**
     * 用户登出
     */
    async logout() {
        await CommonAPI.post('/api/auth/logout').catch(() => {});
        Utils.clearAuth();
        window.location.href = '/frontend/login.html';
    },

    /**
     * 验证 token 是否有效
     */
    async verifyToken() {
        const response = await CommonAPI.get('/api/auth/me');
        
        if (response.success && response.data.success) {
            // 后端返回格式: {success: true, data: {用户信息}}
            // CommonAPI包装后: response.data = {success: true, data: {用户信息}}
            // 所以用户信息在: response.data.data
            const userData = response.data.data;
            Utils.saveUser(userData);
            return { success: true, user: userData };
        } else {
            Utils.clearAuth();
            return { success: false };
        }
    },

    /**
     * 获取院系列表
     */
    async getDepartments() {
        const response = await CommonAPI.get('/api/auth/departments');
        return response.success
            ? { success: true, departments: response.data }
            : { success: false, message: response.error };
    }
};

// 全局导出
window.AuthAPI = AuthAPI;