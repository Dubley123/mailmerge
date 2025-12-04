(function() {
    const AgentUI = {
        currentSessionId: null,
        sessions: [],

        init: async () => {
            AgentUI.bindEvents();
            await AgentUI.loadSessions();
            
            // 如果有会话，默认选中第一个；否则进入新建对话模式
            if (AgentUI.sessions.length > 0) {
                AgentUI.selectSession(AgentUI.sessions[0].id);
            } else {
                AgentUI.enterNewChatMode();
            }
        },

        bindEvents: () => {
            const newChatBtn = document.getElementById('newChatBtn');
            if (newChatBtn) {
                newChatBtn.addEventListener('click', () => {
                    AgentUI.createNewSession();
                });
            }

            const sendBtn = document.getElementById('sendBtn');
            if (sendBtn) {
                sendBtn.addEventListener('click', () => {
                    AgentUI.sendMessage();
                });
            }

            const chatInput = document.getElementById('chatInput');
            if (chatInput) {
                chatInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        AgentUI.sendMessage();
                    }
                });

                chatInput.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = (this.scrollHeight) + 'px';
                    
                    const sendBtn = document.getElementById('sendBtn');
                    if (sendBtn) {
                        sendBtn.disabled = !this.value.trim();
                    }
                });
            }
        },

        loadSessions: async () => {
            try {
                const response = await AgentAPI.getSessions();
                if (response.success) {
                    AgentUI.sessions = response.data;
                    AgentUI.renderSessionList();
                }
            } catch (error) {
                console.error('Failed to load sessions:', error);
            }
        },

        renderSessionList: () => {
            const listContainer = document.getElementById('sessionList');
            if (!listContainer) return;
            
            listContainer.innerHTML = '';

            AgentUI.sessions.forEach(session => {
                const item = document.createElement('div');
                item.className = `session-item ${session.id === AgentUI.currentSessionId ? 'active' : ''}`;
                item.onclick = () => AgentUI.selectSession(session.id);
                
                item.innerHTML = `
                    <div class="session-title">${Utils.escapeHtml(session.title)}</div>
                    <div class="session-actions">
                        <div class="session-action-btn" onclick="event.stopPropagation(); window.AgentUI.deleteSession(${session.id})" title="删除">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                        </div>
                    </div>
                `;
                listContainer.appendChild(item);
            });
        },

        selectSession: async (sessionId) => {
            if (AgentUI.currentSessionId === sessionId) return;
            
            AgentUI.currentSessionId = sessionId;
            
            // 退出新建对话模式
            const chatArea = document.querySelector('.chat-area');
            if (chatArea) chatArea.classList.remove('initial-state');
            
            AgentUI.renderSessionList();
            
            const session = AgentUI.sessions.find(s => s.id === sessionId);
            if (session) {
                const titleEl = document.getElementById('currentChatTitle');
                if (titleEl) titleEl.textContent = session.title;
            }

            await AgentUI.loadMessages(sessionId);
        },

        createNewSession: () => {
            AgentUI.enterNewChatMode();
        },

        enterNewChatMode: () => {
            AgentUI.currentSessionId = null;
            
            // 进入新建对话模式（居中显示）
            const chatArea = document.querySelector('.chat-area');
            if (chatArea) chatArea.classList.add('initial-state');
            
            // 重置消息区域为 Empty State
            const messagesContainer = document.getElementById('chatMessages');
            if (messagesContainer) {
                messagesContainer.innerHTML = `
                    <div class="empty-state" id="emptyState">
                        <div class="empty-state-icon">🤖</div>
                        <div class="empty-state-text">我是您的智能助手</div>
                        <div class="empty-state-subtext">我可以帮您查询数据、创建模板、管理任务等。请在下方输入您的需求。</div>
                    </div>
                `;
            }
            
            // 清空输入框
            const input = document.getElementById('chatInput');
            if (input) {
                input.value = '';
                input.style.height = '56px';
                input.focus();
            }
            
            // 更新侧边栏（取消选中状态）
            AgentUI.renderSessionList();
        },

        deleteSession: async (sessionId) => {
            if (!confirm('确定要删除这个对话吗？')) return;
            
            try {
                const response = await AgentAPI.deleteSession(sessionId);
                if (response.success) {
                    AgentUI.sessions = AgentUI.sessions.filter(s => s.id !== sessionId);
                    
                    if (AgentUI.currentSessionId === sessionId) {
                        if (AgentUI.sessions.length > 0) {
                            AgentUI.selectSession(AgentUI.sessions[0].id);
                        } else {
                            AgentUI.enterNewChatMode();
                        }
                    } else {
                        AgentUI.renderSessionList();
                    }
                }
            } catch (error) {
                console.error('Failed to delete session:', error);
            }
        },

        loadMessages: async (sessionId) => {
            const messagesContainer = document.getElementById('chatMessages');
            if (!messagesContainer) return;
            
            messagesContainer.innerHTML = '<div class="loading-spinner" style="text-align:center; padding:20px;">加载中...</div>';
            
            try {
                const response = await AgentAPI.getMessages(sessionId);
                if (response.success) {
                    const messages = response.data;
                    messagesContainer.innerHTML = '';
                    
                    if (messages.length === 0) {
                        messagesContainer.innerHTML = `
                            <div class="empty-state" id="emptyState">
                                <div class="empty-state-icon">🤖</div>
                                <div class="empty-state-text">我是您的智能助手</div>
                                <div class="empty-state-subtext">我可以帮您查询数据、创建模板、管理任务等。请在下方输入您的需求。</div>
                            </div>
                        `;
                    } else {
                        messages.forEach(msg => AgentUI.appendMessage(msg.role, msg.content));
                        AgentUI.scrollToBottom();
                    }
                }
            } catch (error) {
                console.error('Failed to load messages:', error);
                messagesContainer.innerHTML = '<div class="error-message">加载消息失败</div>';
            }
        },

        sendMessage: async () => {
            console.log('sendMessage called');
            const input = document.getElementById('chatInput');
            if (!input) {
                console.error('chatInput not found');
                return;
            }
            
            const content = input.value.trim();
            if (!content) {
                console.log('Content is empty');
                return;
            }

            // 懒加载创建会话逻辑：如果当前没有会话ID，先创建会话
            if (!AgentUI.currentSessionId) {
                try {
                    console.log('Creating new session lazily...');
                    const response = await AgentAPI.createSession();
                    if (response.success) {
                        const newSession = response.data;
                        AgentUI.currentSessionId = newSession.id;
                        AgentUI.sessions.unshift(newSession);
                        
                        // 退出新建对话模式
                        const chatArea = document.querySelector('.chat-area');
                        if (chatArea) chatArea.classList.remove('initial-state');
                        
                        // 更新标题
                        const titleEl = document.getElementById('currentChatTitle');
                        if (titleEl) titleEl.textContent = newSession.title;
                        
                        // 清除 Empty State
                        const messagesContainer = document.getElementById('chatMessages');
                        if (messagesContainer) messagesContainer.innerHTML = '';
                        
                        AgentUI.renderSessionList();
                    } else {
                        throw new Error('Failed to create session');
                    }
                } catch (error) {
                    console.error('Create session failed:', error);
                    alert('创建会话失败，请刷新页面重试。');
                    return;
                }
            }

            input.value = '';
            input.style.height = '56px';
            const sendBtn = document.getElementById('sendBtn');
            if (sendBtn) sendBtn.disabled = true;
            input.disabled = true;

            const emptyState = document.getElementById('emptyState');
            if (emptyState) emptyState.remove();

            AgentUI.appendMessage('user', content);
            AgentUI.scrollToBottom();

            const loadingId = AgentUI.appendLoading();
            AgentUI.scrollToBottom();

            try {
                console.log('Sending message to API...');
                const response = await AgentAPI.sendMessage(AgentUI.currentSessionId, content);
                console.log('API Response:', response);
                
                if (response.success) {
                    const msg = response.data;
                    AgentUI.appendMessage('assistant', msg.content);
                    
                    const session = AgentUI.sessions.find(s => s.id === AgentUI.currentSessionId);
                    // 如果标题以"新对话"开头（包括自动生成的序号），则根据内容更新标题
                    // 使用正则匹配：^新对话\d*$
                    if (session && /^新对话\d*$/.test(session.title)) {
                        try {
                            const newTitle = content.substring(0, 15) + (content.length > 15 ? '...' : '');
                            await AgentAPI.updateSession(AgentUI.currentSessionId, newTitle);
                            session.title = newTitle;
                            const titleEl = document.getElementById('currentChatTitle');
                            if (titleEl) titleEl.textContent = newTitle;
                            AgentUI.renderSessionList();
                        } catch (updateError) {
                            console.error('Failed to update session title:', updateError);
                            // 标题更新失败不影响消息展示，忽略错误
                        }
                    }
                    
                    // 将当前会话移到列表顶部
                    AgentUI.sessions = AgentUI.sessions.filter(s => s.id !== AgentUI.currentSessionId);
                    if (session) AgentUI.sessions.unshift(session);
                    AgentUI.renderSessionList();
                    
                } else {
                    AgentUI.appendMessage('assistant', '抱歉，处理您的请求时出现错误。');
                }
            } catch (error) {
                AgentUI.appendMessage('assistant', '网络请求失败，请稍后重试。');
                console.error('Send message failed:', error);
            } finally {
                const loadingEl = document.getElementById(loadingId);
                if (loadingEl) loadingEl.remove();
                
                if (sendBtn) sendBtn.disabled = false;
                input.disabled = false;
                input.focus();
                AgentUI.scrollToBottom();
            }
        },

        appendMessage: (role, content) => {
            const container = document.getElementById('chatMessages');
            if (!container) return;
            
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${role}`;
            
            let contentHtml = '';
            
            if (typeof content === 'object' && content !== null && content.items) {
                // Structured response
                content.items.forEach(item => {
                    if (item.format === 'text') {
                        let text = Utils.escapeHtml(item.content)
                            .replace(/\n/g, '<br>')
                            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                        contentHtml += `<div class="message-text">${text}</div>`;
                    } else if (item.format === 'table') {
                        contentHtml += AgentUI.renderTable(item.content);
                    }
                });
            } else {
                // Legacy string response
                let text = Utils.escapeHtml(String(content))
                    .replace(/\n/g, '<br>')
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                contentHtml = `<div class="message-text">${text}</div>`;
            }
            
            msgDiv.innerHTML = `
                <div class="message-avatar">
                    ${role === 'user' ? '👤' : '🤖'}
                </div>
                <div class="message-content">
                    ${contentHtml}
                </div>
            `;
            
            container.appendChild(msgDiv);
        },

        renderTable: (tableData) => {
            if (!tableData || !tableData.columns || !tableData.rows) return '';
            
            const columns = tableData.columns;
            const rows = tableData.rows;
            
            let html = '<div class="table-container"><table><thead><tr>';
            columns.forEach(col => {
                html += `<th>${Utils.escapeHtml(col)}</th>`;
            });
            html += '</tr></thead><tbody>';
            
            rows.forEach(row => {
                html += '<tr>';
                row.forEach(cell => {
                    // Handle null/undefined values
                    const cellValue = cell === null || cell === undefined ? '' : String(cell);
                    html += `<td>${Utils.escapeHtml(cellValue)}</td>`;
                });
                html += '</tr>';
            });
            
            html += '</tbody></table></div>';
            return html;
        },

        appendLoading: () => {
            const container = document.getElementById('chatMessages');
            if (!container) return null;
            
            const id = 'loading-' + Date.now();
            const msgDiv = document.createElement('div');
            msgDiv.id = id;
            msgDiv.className = 'message assistant';
            msgDiv.innerHTML = `
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            `;
            container.appendChild(msgDiv);
            return id;
        },

        scrollToBottom: () => {
            const container = document.getElementById('chatMessages');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }
    };

    // Export to window so we can call deleteSession from HTML onclick
    window.AgentUI = AgentUI;

    // Initialize
    AgentUI.init();
})();