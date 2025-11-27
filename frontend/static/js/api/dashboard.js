/**
 * Dashboard API 客户端
 * 处理首页概览数据请求
 */

const DashboardAPI = {
    /**
     * 获取首页概览数据
     * @returns {Promise<Object>} 包含个人信息、任务统计、邮件统计
     */
    async getOverview() {
        const result = await CommonAPI.get('/api/dashboard/overview');
        
        if (result.success) {
            return {
                success: true,
                data: result.data
            };
        } else {
            return {
                success: false,
                message: result.error || '获取数据失败'
            };
        }
    }
};