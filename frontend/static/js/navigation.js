/**
 * 页面导航管理
 * 负责主界面子页面的动态加载和切换
 */

const Navigation = {
    // 当前激活的页面
    currentPage: 'dashboard',

    // 页面容器
    contentContainer: null,

    /**
     * 初始化导航
     */
    init() {
        this.contentContainer = document.getElementById('app');
        
        // 绑定导航点击事件
        this.bindNavigation();
        
        // 加载默认页面
        this.loadPage('dashboard');
    },

    /**
     * 绑定导航点击事件
     */
    bindNavigation() {
        const navLinks = document.querySelectorAll('.sidebar-nav-link');
        
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = link.getAttribute('data-page');
                this.loadPage(page);
            });
        });
    },

    /**
     * 加载指定页面
     */
    async loadPage(pageName) {
        if (!this.contentContainer) {
            console.error('内容容器未找到');
            return;
        }

        try {
            // 显示加载状态
            this.contentContainer.innerHTML = '<div class="loading-container" style="padding: 40px; text-align: center;">加载中...</div>';

            // 获取页面内容（添加时间戳避免缓存）
            const timestamp = new Date().getTime();
            const response = await fetch(`/frontend/pages/${pageName}.html?t=${timestamp}`);
            
            if (!response.ok) {
                throw new Error('页面加载失败');
            }

            const html = await response.text();
            
            // 更新内容
            this.contentContainer.innerHTML = html;
            
            // 等待 DOM 解析完成
            await new Promise(resolve => setTimeout(resolve, 0));
            
            // 执行页面中的脚本（包括外部脚本）
            await this.executeScripts(this.contentContainer);
            
            // 更新当前页面
            this.currentPage = pageName;
            
            // 更新导航激活状态
            this.updateActiveNav(pageName);
            
            // 触发页面加载完成事件
            this.onPageLoaded(pageName);
            
        } catch (error) {
            console.error('加载页面失败:', error);
            this.contentContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⚠️</div>
                    <div class="empty-state-text">页面加载失败</div>
                </div>
            `;
        }
    },

    /**
     * 更新导航激活状态
     */
    updateActiveNav(pageName) {
        const navLinks = document.querySelectorAll('.sidebar-nav-link');
        
        navLinks.forEach(link => {
            const linkPage = link.getAttribute('data-page');
            if (linkPage === pageName) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    },

    /**
     * 执行页面中的脚本
     */
    async executeScripts(container) {
        const scripts = container.querySelectorAll('script');
        
        for (const oldScript of scripts) {
            const newScript = document.createElement('script');
            
            // 复制所有属性
            Array.from(oldScript.attributes).forEach(attr => {
                newScript.setAttribute(attr.name, attr.value);
            });
            
            // 如果是外部脚本
            if (oldScript.src) {
                // 创建 Promise 来等待脚本加载
                await new Promise((resolve, reject) => {
                    newScript.onload = resolve;
                    newScript.onerror = reject;
                    newScript.src = oldScript.src;
                    document.body.appendChild(newScript);
                });
            } else {
                // 内联脚本
                newScript.textContent = oldScript.textContent;
                document.body.appendChild(newScript);
            }
            
            // 移除旧脚本标签
            oldScript.remove();
        }
    },

    /**
     * 页面加载完成回调
     */
    onPageLoaded(pageName) {
        console.log(`页面已加载: ${pageName}`);
    },

    /**
     * 重新加载当前页面
     */
    reload() {
        this.loadPage(this.currentPage);
    },

    /**
     * 获取当前页面名称
     */
    getCurrentPage() {
        return this.currentPage;
    },
};

// 全局导出
window.Navigation = Navigation;
