/**
 * 模板相关 API 客户端
 */

const TemplateAPI = {
    /**
     * 获取所有模板
     */
    async getTemplates() {
        const result = await CommonAPI.get('/api/templates/');
        if (result.success) {
            return Array.isArray(result.data) ? result.data : [];
        }
        throw new Error(result.error || '获取模板列表失败');
    },

    /**
     * 获取模板详情
     */
    async getTemplateDetail(templateId) {
        const result = await CommonAPI.get(`/api/templates/${templateId}`);
        if (result.success) {
            return result.data;
        }
        throw new Error(result.error || '获取模板详情失败');
    },

    /**
     * 创建模板
     */
    async createTemplate(data) {
        const result = await CommonAPI.post('/api/templates/create', data);
        if (result.success) {
            return result.data;
        }
        throw new Error(result.error || '创建模板失败');
    },

    /**
     * 更新模板
     */
    async updateTemplate(templateId, data) {
        const result = await CommonAPI.put(`/api/templates/${templateId}`, data);
        if (result.success) {
            return result.data;
        }
        throw new Error(result.error || '更新模板失败');
    },

    /**
     * 删除模板
     */
    async deleteTemplate(templateId) {
        const result = await CommonAPI.delete(`/api/templates/${templateId}`);
        if (result.success) {
            return result.data;
        }
        throw new Error(result.error || '删除模板失败');
    },

    /**
     * 解析 Excel 文件
     */
    async parseExcel(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/templates/parse-excel', {
                method: 'POST',
                headers: {
                    ...Utils.getAuthHeaders(),
                },
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '解析 Excel 失败');
            }

            return await response.json();
        } catch (error) {
            console.error('解析 Excel 错误:', error);
            throw error;
        }
    }
};
