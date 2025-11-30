window.MailboxAPI = {
    /**
     * Get all tasks with email counts
     * @returns {Promise<Array>} List of tasks
     */
    getTasks: async () => {
        const result = await CommonAPI.get('/api/mailbox/tasks');
        if (result.success) {
            return result.data;
        }
        throw new Error(result.message || 'Failed to fetch tasks');
    },

    /**
     * Get emails for a specific task
     * @param {number} taskId 
     * @param {string} type 'sent' or 'received'
     * @returns {Promise<Array>} List of emails
     */
    getEmails: async (taskId, type) => {
        const result = await CommonAPI.get(`/api/mailbox/tasks/${taskId}/emails`, { type });
        if (result.success) {
            return result.data;
        }
        throw new Error(result.message || 'Failed to fetch emails');
    }
};
