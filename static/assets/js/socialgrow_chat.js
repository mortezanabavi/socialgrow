(function() {
    // Avoid double initialization
    if (window.SGChatWidgetLoaded) return;
    window.SGChatWidgetLoaded = true;

    const STORAGE_READ_KEY = 'sg_chat_last_read_id';
    let lastReadId = parseInt(localStorage.getItem(STORAGE_READ_KEY) || '0', 10);
    let lastMessageId = 0;
    let pollInterval = null;
    let isOpen = false;
    let hasLoadedHistory = false;
    let unreadCount = 0;

    // Inject Widget HTML
    const widgetHtml = `
    <div id="sg-chat-widget-root">
        <!-- Floating Launcher -->
        <button class="sg-chat-launcher" id="sg-chat-launcher-btn" title="پشتیبانی آنلاین سوشال گرو" aria-label="پشتیبانی آنلاین">
            <i class="fa-solid fa-headset sg-icon-open"></i>
            <i class="fa-solid fa-xmark sg-icon-close"></i>
            <span class="sg-chat-unread-badge" id="sg-chat-badge">0</span>
        </button>

        <!-- Chat Box -->
        <div class="sg-chat-box" id="sg-chat-box">
            <!-- Header -->
            <div class="sg-chat-header">
                <div class="sg-chat-header-info">
                    <div class="sg-chat-avatar">
                        <i class="fa-solid fa-headset"></i>
                        <span class="sg-chat-status-dot"></span>
                    </div>
                    <div>
                        <div class="sg-chat-title">پشتیبانی آنلاین سوشال گرو</div>
                        <div class="sg-chat-subtitle">
                            <span class="sg-chat-tg-badge"><i class="fa-brands fa-telegram"></i> پاسخگویی سریع</span>
                            پاسخگوی سوالات شما هستیم
                        </div>
                    </div>
                </div>
                <div class="sg-chat-header-actions">
                    <button class="sg-chat-header-btn" id="sg-chat-close-btn" title="بستن چت">
                        <i class="fa-solid fa-chevron-down"></i>
                    </button>
                </div>
            </div>

            <!-- Messages Container -->
            <div class="sg-chat-messages" id="sg-chat-messages-container">
                <div class="sg-chat-welcome">
                    سلام! 👋 به پشتیبانی سوشال گرو خوش آمدید. هر سوالی در رابطه با سرویس‌ها، ثبت سفارش یا پیگیری دارید بفرمایید، کارشناسان ما به سرعت پاسخگوی شما خواهند بود.
                </div>
            </div>

            <!-- Input Area -->
            <div class="sg-chat-input-area">
                <div class="sg-chat-user-fields" id="sg-chat-user-fields" style="display:none;">
                    <input type="text" id="sg-chat-input-name" placeholder="نام شما (اختیاری)">
                    <input type="text" id="sg-chat-input-contact" placeholder="شماره تماس یا آیدی تلگرام">
                </div>
                <div class="sg-chat-input-form">
                    <textarea class="sg-chat-textarea" id="sg-chat-textarea" placeholder="پیام خود را بنویسید..." rows="1"></textarea>
                    <button class="sg-chat-send-btn" id="sg-chat-send-btn" title="ارسال پیام" aria-label="ارسال">
                        <i class="fa-solid fa-paper-plane" id="sg-send-fa-icon"></i>
                        <svg class="sg-send-icon" id="sg-send-svg-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;">
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    </div>
    `;

    document.body.insertAdjacentHTML('beforeend', widgetHtml);

    // Elements
    const rootEl = document.getElementById('sg-chat-widget-root');
    const launcherBtn = document.getElementById('sg-chat-launcher-btn');
    const closeBtn = document.getElementById('sg-chat-close-btn');
    const messagesContainer = document.getElementById('sg-chat-messages-container');
    const textarea = document.getElementById('sg-chat-textarea');
    const sendBtn = document.getElementById('sg-chat-send-btn');
    const userFields = document.getElementById('sg-chat-user-fields');
    const nameInput = document.getElementById('sg-chat-input-name');
    const contactInput = document.getElementById('sg-chat-input-contact');
    const badgeEl = document.getElementById('sg-chat-badge');

    // Auto-scroll messages
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Mark Chat As Read
    function markChatAsRead() {
        if (lastMessageId > lastReadId) {
            lastReadId = lastMessageId;
        }
        try {
            localStorage.setItem(STORAGE_READ_KEY, String(lastReadId));
        } catch (e) {}
        unreadCount = 0;
        badgeEl.style.display = 'none';
        badgeEl.innerText = '0';

        // Notify server that messages are read
        fetch('/api/chat/read/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'same-origin'
        }).catch(() => {});
    }

    // Format Message Node
    function appendMessageNode(msg) {
        const row = document.createElement('div');
        row.className = `sg-msg-row ${msg.sender === 'user' ? 'sg-msg-user' : 'sg-msg-admin'}`;
        row.id = `sg-msg-${msg.id}`;

        const bubble = document.createElement('div');
        bubble.className = 'sg-msg-bubble';
        bubble.innerText = msg.text;

        const time = document.createElement('div');
        time.className = 'sg-msg-time';
        time.innerText = msg.created_at || '';

        row.appendChild(bubble);
        row.appendChild(time);
        messagesContainer.appendChild(row);

        if (msg.id > lastMessageId) {
            lastMessageId = msg.id;
        }

        // If chat is open while a new message arrives, mark it read immediately
        if (isOpen && msg.id > lastReadId) {
            lastReadId = msg.id;
            try {
                localStorage.setItem(STORAGE_READ_KEY, String(lastReadId));
            } catch (e) {}
        }
    }

    // Initialize or Fetch History
    function loadChatHistory() {
        fetch('/api/chat/init/', { credentials: 'same-origin' })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    if (!data.is_authenticated && (!data.name && !data.phone_or_email)) {
                        userFields.style.display = 'flex';
                    } else {
                        userFields.style.display = 'none';
                    }

                    if (data.name) nameInput.value = data.name;
                    if (data.phone_or_email) contactInput.value = data.phone_or_email;

                    if (data.messages && data.messages.length > 0) {
                        data.messages.forEach(m => {
                            if (!document.getElementById(`sg-msg-${m.id}`)) {
                                appendMessageNode(m);
                            }
                        });
                        scrollToBottom();
                    }
                    hasLoadedHistory = true;

                    if (isOpen) {
                        markChatAsRead();
                    } else {
                        // Unread messages: admin sender, id > lastReadId, and !m.is_read
                        const unreadAdminMsgs = (data.messages || []).filter(m => 
                            m.sender === 'admin' && m.id > lastReadId && !m.is_read
                        );
                        unreadCount = unreadAdminMsgs.length;
                        if (unreadCount > 0) {
                            badgeEl.innerText = unreadCount;
                            badgeEl.style.display = 'flex';
                        } else {
                            badgeEl.innerText = '0';
                            badgeEl.style.display = 'none';
                        }
                    }
                }
            })
            .catch(err => console.error('Error init chat:', err));
    }

    // Polling for new messages
    function pollNewMessages() {
        fetch(`/api/chat/poll/?last_id=${lastMessageId}&is_open=${isOpen ? 1 : 0}`, { credentials: 'same-origin' })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.messages && data.messages.length > 0) {
                    data.messages.forEach(m => {
                        if (!document.getElementById(`sg-msg-${m.id}`)) {
                            appendMessageNode(m);
                        }
                    });
                    scrollToBottom();

                    if (isOpen) {
                        markChatAsRead();
                    } else {
                        const newUnreadAdminMsgs = data.messages.filter(m => 
                            m.sender === 'admin' && m.id > lastReadId && !m.is_read
                        );
                        if (newUnreadAdminMsgs.length > 0) {
                            unreadCount += newUnreadAdminMsgs.length;
                            badgeEl.innerText = unreadCount;
                            badgeEl.style.display = 'flex';
                        }
                    }
                }
            })
            .catch(err => console.error('Error polling chat:', err));
    }

    // Send Message
    function sendMessage() {
        const text = textarea.value.trim();
        if (!text) return;

        sendBtn.disabled = true;

        const payload = {
            text: text,
            name: nameInput ? nameInput.value.trim() : '',
            phone_or_email: contactInput ? contactInput.value.trim() : ''
        };

        fetch('/api/chat/send/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            body: JSON.stringify(payload),
            credentials: 'same-origin'
        })
        .then(res => res.json())
        .then(data => {
            sendBtn.disabled = false;
            if (data.status === 'success' && data.message) {
                textarea.value = '';
                textarea.style.height = '44px';
                if (!document.getElementById(`sg-msg-${data.message.id}`)) {
                    appendMessageNode(data.message);
                }
                scrollToBottom();

                // If user provided contact info, hide user fields
                if (payload.phone_or_email) {
                    userFields.style.display = 'none';
                }
            } else {
                alert(data.message || 'خطا در ارسال پیام. لطفاً دوباره تلاش کنید.');
            }
        })
        .catch(err => {
            sendBtn.disabled = false;
            console.error('Error sending message:', err);
        });
    }

    // Toggle Chat Window
    function toggleChat(open) {
        isOpen = (open !== undefined) ? open : !isOpen;
        if (isOpen) {
            rootEl.classList.add('sg-chat-open');
            markChatAsRead();
            if (!hasLoadedHistory) {
                loadChatHistory();
            }
            scrollToBottom();
            setTimeout(() => textarea.focus(), 300);

            if (!pollInterval) {
                pollInterval = setInterval(pollNewMessages, 3500);
            }
        } else {
            rootEl.classList.remove('sg-chat-open');
        }
    }

    // Cookie helper
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Event Listeners
    launcherBtn.addEventListener('click', () => toggleChat());
    closeBtn.addEventListener('click', () => toggleChat(false));

    sendBtn.addEventListener('click', sendMessage);

    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    textarea.addEventListener('input', () => {
        textarea.style.height = '44px';
        textarea.style.height = Math.min(textarea.scrollHeight, 100) + 'px';
    });

    // Global hook for external buttons like footer links
    window.openSocialGrowChat = function(e) {
        if (e && e.preventDefault) e.preventDefault();
        toggleChat(true);
    };

    // Fallback detection for FontAwesome
    setTimeout(() => {
        const faIcon = document.getElementById('sg-send-fa-icon');
        const svgIcon = document.getElementById('sg-send-svg-icon');
        if (faIcon && svgIcon) {
            const width = faIcon.offsetWidth;
            // If font didn't load or glyph is missing, width is 0
            if (width === 0) {
                faIcon.style.display = 'none';
                svgIcon.style.display = 'block';
            }
        }
    }, 1200);

    // Sync read status across tabs
    window.addEventListener('storage', (e) => {
        if (e.key === STORAGE_READ_KEY) {
            lastReadId = parseInt(e.newValue || '0', 10);
            if (lastMessageId <= lastReadId) {
                unreadCount = 0;
                badgeEl.style.display = 'none';
                badgeEl.innerText = '0';
            }
        }
    });

    // Automatically load chat history on page load to prime message IDs and read status
    loadChatHistory();

    // Pre-poll occasionally in background for incoming replies even when closed
    setInterval(pollNewMessages, 7000);
})();
