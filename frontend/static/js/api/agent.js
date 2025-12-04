/**
 * Agent API 模块
 * 处理与智能助手相关的 API 请求
 */

const AgentAPI = {
    /**
     * 获取会话列表
     */
    getSessions: async () => {
        return await CommonAPI.get('/api/agent/sessions');
    },

    /**
     * 创建新会话
     * @param {string} title - 会话标题
     */
    createSession: async (title = "新对话") => {
        return await CommonAPI.post('/api/agent/sessions', { title });
    },

    /**
     * 获取会话消息
     * @param {number} sessionId - 会话ID
     */
    getMessages: async (sessionId) => {
        return await CommonAPI.get(`/api/agent/sessions/${sessionId}/messages`);
    },

    /**
     * 发送消息
     * @param {number} sessionId - 会话ID
     * @param {string} content - 消息内容
     */
    sendMessage: async (sessionId, content) => {
        return await CommonAPI.post(`/api/agent/sessions/${sessionId}/messages`, { content });
    },

    /**
     * 删除会话
     * @param {number} sessionId - 会话ID
     */
    deleteSession: async (sessionId) => {
        return await CommonAPI.delete(`/api/agent/sessions/${sessionId}`);
    },

    /**
     * 更新会话标题
     * @param {number} sessionId - 会话ID
     * @param {string} title - 新标题
     */
    updateSession: async (sessionId, title) => {
        return await CommonAPI.patch(`/api/agent/sessions/${sessionId}`, { title });
    }
};

// 导出到全局 window 对象 (如果项目使用这种方式)
window.AgentAPI = AgentAPI;
