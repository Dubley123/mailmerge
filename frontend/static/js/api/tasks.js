/**
 * Tasks API 客户端
 * 处理任务相关的 API 请求
 */

const TasksAPI = {
    /**
     * 获取任务列表
     */
    async getTaskList() {
        const result = await CommonAPI.get('/api/tasks/list');
        if (result.success) {
            // 后端返回的直接是数组
            return { success: true, data: Array.isArray(result.data) ? result.data : [] };
        }
        return { success: false, message: result.error || '获取任务列表失败', data: [] };
    },

    /**
     * 获取任务详情
     */
    async getTaskDetail(taskId) {
        const result = await CommonAPI.get(`/api/tasks/${taskId}`);
        return result.success
            ? { success: true, data: result.data }
            : { success: false, message: result.error || '获取任务详情失败' };
    },

    /**
     * 创建任务
     */
    async createTask(taskData) {
        const result = await CommonAPI.post('/api/tasks/create', taskData);
        return result.success
            ? { success: true, message: '任务创建成功', data: result.data }
            : { success: false, message: result.error || '创建任务失败' };
    },

    /**
     * 更新任务
     */
    async updateTask(taskId, taskData) {
        const result = await CommonAPI.put(`/api/tasks/${taskId}`, taskData);
        return result.success
            ? { success: true, message: '任务更新成功' }
            : { success: false, message: result.error || '更新任务失败' };
    },

    /**
     * 关闭任务
     */
    async closeTask(taskId) {
        const result = await CommonAPI.post(`/api/tasks/${taskId}/close`);
        return result.success
            ? { success: true, message: '任务已关闭' }
            : { success: false, message: result.error || '关闭任务失败' };
    },

    /**
     * 发布任务
     */
    async publishTask(taskId) {
        const result = await CommonAPI.post(`/api/tasks/${taskId}/publish`);
        return result.success
            ? { success: true, message: '任务已发布' }
            : { success: false, message: result.error || '发布任务失败' };
    },

    /**
     * 合并并导出任务数据
     */
    async aggregateTask(taskId) {
        const result = await CommonAPI.post(`/api/tasks/${taskId}/aggregate`);
        return result.success
            ? { success: true, message: '合并导出成功', data: result.data }
            : { success: false, message: result.error || '合并导出失败' };
    },

    /**
     * 获取模板列表
     */
    async getTemplates() {
        const result = await CommonAPI.get('/api/templates/list');
        if (result.success) {
            return { success: true, data: Array.isArray(result.data) ? result.data : [] };
        }
        return { success: false, message: result.error || '获取模板列表失败', data: [] };
    },

    /**
     * 获取教师列表
     */
    async getTeachers() {
        const result = await CommonAPI.get('/api/teachers/list');
        if (result.success) {
            return { success: true, data: Array.isArray(result.data) ? result.data : [] };
        }
        return { success: false, message: result.error || '获取教师列表失败', data: [] };
    }
};

// 全局导出
window.TasksAPI = TasksAPI;
