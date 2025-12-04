/**
 * Fetch 封装和通用错误处理
 * 提供统一的 API 调用接口
 */

const API = {
    baseURL: '',

    /**
     * 通用请求方法
     */
    async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...Utils.getAuthHeaders(),
            },
        };

        const config = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers,
            },
        };

        try {
            const response = await fetch(this.baseURL + url, config);
            
            // 处理 401 未授权
            if (response.status === 401) {
                Utils.clearAuth();
                window.location.href = '/frontend/login.html';
                throw new Error('未授权，请重新登录');
            }

            // 处理 404
            if (response.status === 404) {
                throw new Error('请求的资源不存在');
            }

            // 处理 500 服务器错误
            if (response.status >= 500) {
                throw new Error('服务器错误，请稍后再试');
            }

            // 解析响应
            const contentType = response.headers.get('content-type');
            let data;
            
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            // 检查响应状态
            if (!response.ok) {
                // 提取错误信息（优先使用 detail，其次 message）
                const errorMsg = data.detail || data.message || '请求失败';
                throw new Error(errorMsg);
            }

            return {
                success: true,
                data: data,
                status: response.status,
            };
        } catch (error) {
            console.error('API 请求错误:', error);
            return {
                success: false,
                error: error.message || '网络连接失败',
            };
        }
    },

    /**
     * GET 请求
     */
    async get(url, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullURL = queryString ? `${url}?${queryString}` : url;
        return this.request(fullURL, { method: 'GET' });
    },

    /**
     * POST 请求
     */
    async post(url, data = {}) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    /**
     * PUT 请求
     */
    async put(url, data = {}) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },

    /**
     * PATCH 请求
     */
    async patch(url, data = {}) {
        return this.request(url, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    },

    /**
     * DELETE 请求
     */
    async delete(url) {
        return this.request(url, { method: 'DELETE' });
    },

    /**
     * 上传文件
     */
    async upload(url, file, fieldName = 'file') {
        const formData = new FormData();
        formData.append(fieldName, file);

        return this.request(url, {
            method: 'POST',
            headers: {
                ...Utils.getAuthHeaders(),
            },
            body: formData,
        });
    },
};

// 全局导出
window.CommonAPI = API;