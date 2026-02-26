/**
 * EntertainBot — Modern Chat UI Logic
 *
 * Features:
 * - Session management (UUID-based)
 * - Message sending/receiving via POST /chat
 * - Streaming typing animation (character-by-character reveal)
 * - Markdown rendering (via marked.js)
 * - Auto-resize textarea
 * - Suggestion card interaction
 * - Mobile sidebar toggle
 * - Smooth auto-scroll
 */

(function () {
    'use strict';

    // ── DOM Elements ──────────────────────────────────────────────────
    const chatMessages = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const clearBtn = document.getElementById('clearBtn');
    const clearBtnMobile = document.getElementById('clearBtnMobile');
    const welcomeMessage = document.getElementById('welcomeMessage');
    const menuBtn = document.getElementById('menuBtn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    // ── State ─────────────────────────────────────────────────────────
    let sessionId = generateSessionId();
    let isProcessing = false;

    // ── Streaming config ──────────────────────────────────────────────
    const CHAR_DELAY = 8;          // ms per character
    const CHUNK_SIZE = 3;          // characters per tick
    const INITIAL_DELAY = 100;     // ms before streaming starts

    // ── Marked.js Configuration ───────────────────────────────────────
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
        });
    }

    // ── Event Listeners ───────────────────────────────────────────────
    chatForm.addEventListener('submit', handleSubmit);
    chatInput.addEventListener('input', handleInputChange);
    chatInput.addEventListener('keydown', handleKeydown);
    clearBtn.addEventListener('click', handleClearChat);
    if (clearBtnMobile) clearBtnMobile.addEventListener('click', handleClearChat);

    // Mobile sidebar toggle
    if (menuBtn) {
        menuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarOverlay.classList.toggle('active');
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
    }

    // Suggestion cards
    document.querySelectorAll('.suggestion-card').forEach(card => {
        card.addEventListener('click', () => {
            const message = card.getAttribute('data-message');
            if (message) {
                chatInput.value = message;
                autoResizeTextarea();
                handleInputChange();
                handleSubmit(new Event('submit'));
            }
        });
    });

    // Nav items (visual only for now)
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            // Close sidebar on mobile
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
    });

    // ── Handlers ──────────────────────────────────────────────────────

    function handleSubmit(e) {
        e.preventDefault();

        const message = chatInput.value.trim();
        if (!message || isProcessing) return;

        // Hide welcome screen
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        // Add user message to UI
        appendMessage('user', message);
        chatInput.value = '';
        autoResizeTextarea();
        handleInputChange();

        // Show typing indicator and send
        showTypingIndicator();
        sendMessage(message);
    }

    function handleInputChange() {
        sendBtn.disabled = !chatInput.value.trim() || isProcessing;
    }

    function handleKeydown(e) {
        // Enter sends, Shift+Enter adds newline
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(new Event('submit'));
        }
    }

    async function handleClearChat() {
        // Clear on server
        try {
            await fetch('/chat/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId }),
            });
        } catch (e) { /* ignore */ }

        // Reset UI
        sessionId = generateSessionId();
        const allMessages = chatMessages.querySelectorAll('.message-row, .typing-row');
        allMessages.forEach(msg => msg.remove());

        if (welcomeMessage) {
            welcomeMessage.style.display = 'flex';
        }

        // Close sidebar on mobile
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('active');
    }

    // ── API Communication ─────────────────────────────────────────────

    async function sendMessage(message) {
        isProcessing = true;
        handleInputChange();

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: sessionId,
                }),
            });

            const data = await response.json();
            hideTypingIndicator();

            if (data.success) {
                sessionId = data.session_id || sessionId;
                appendMessageStreaming('bot', data.response);
            } else {
                const errorMsg = data.error?.message || 'Something went wrong. Please try again.';
                appendMessage('error', errorMsg);
                isProcessing = false;
                handleInputChange();
                chatInput.focus();
            }
        } catch (error) {
            hideTypingIndicator();
            appendMessage('error', 'Network error. Please check your connection and try again.');
            isProcessing = false;
            handleInputChange();
            chatInput.focus();
        }
    }

    // ── UI Helpers ────────────────────────────────────────────────────

    function appendMessage(type, content) {
        const row = document.createElement('div');
        row.classList.add('message-row', `message-row-${type}`);

        const inner = document.createElement('div');
        inner.classList.add('message-inner');

        // Avatar
        const avatar = document.createElement('div');
        avatar.classList.add('msg-avatar');

        // Body
        const body = document.createElement('div');
        body.classList.add('msg-body');

        const sender = document.createElement('div');
        sender.classList.add('msg-sender');

        const textDiv = document.createElement('div');
        textDiv.classList.add('msg-text');

        if (type === 'user') {
            avatar.classList.add('msg-avatar-user');
            avatar.textContent = '👤';
            sender.textContent = 'You';
            textDiv.textContent = content;
        } else if (type === 'bot') {
            avatar.classList.add('msg-avatar-bot');
            avatar.textContent = '✦';
            sender.textContent = 'EntertainBot';
            if (typeof marked !== 'undefined') {
                textDiv.innerHTML = marked.parse(content);
            } else {
                textDiv.textContent = content;
            }
        } else if (type === 'error') {
            row.classList.add('msg-error');
            avatar.classList.add('msg-avatar-bot');
            avatar.textContent = '⚠';
            sender.textContent = 'Error';
            textDiv.textContent = content;
        }

        body.appendChild(sender);
        body.appendChild(textDiv);
        inner.appendChild(avatar);
        inner.appendChild(body);
        row.appendChild(inner);
        chatMessages.appendChild(row);
        scrollToBottom();
    }

    function appendMessageStreaming(type, content) {
        const row = document.createElement('div');
        row.classList.add('message-row', `message-row-${type}`);

        const inner = document.createElement('div');
        inner.classList.add('message-inner');

        // Avatar
        const avatar = document.createElement('div');
        avatar.classList.add('msg-avatar', 'msg-avatar-bot');
        avatar.textContent = '✦';

        // Body
        const body = document.createElement('div');
        body.classList.add('msg-body');

        const sender = document.createElement('div');
        sender.classList.add('msg-sender');
        sender.textContent = 'EntertainBot';

        const textDiv = document.createElement('div');
        textDiv.classList.add('msg-text');

        // Cursor element
        const cursor = document.createElement('span');
        cursor.classList.add('streaming-cursor');

        body.appendChild(sender);
        body.appendChild(textDiv);
        textDiv.appendChild(cursor);
        inner.appendChild(avatar);
        inner.appendChild(body);
        row.appendChild(inner);
        chatMessages.appendChild(row);
        scrollToBottom();

        // Stream the content character-by-character
        streamText(textDiv, cursor, content);
    }

    function streamText(container, cursor, fullText) {
        let charIndex = 0;
        const textNode = document.createTextNode('');
        container.insertBefore(textNode, cursor);

        setTimeout(() => {
            const interval = setInterval(() => {
                if (charIndex >= fullText.length) {
                    clearInterval(interval);
                    // Remove cursor and render final markdown
                    cursor.remove();
                    if (typeof marked !== 'undefined') {
                        container.innerHTML = marked.parse(fullText);
                    } else {
                        container.textContent = fullText;
                    }
                    // Re-enable input
                    isProcessing = false;
                    handleInputChange();
                    chatInput.focus();
                    scrollToBottom();
                    return;
                }

                // Add chunk of characters
                const end = Math.min(charIndex + CHUNK_SIZE, fullText.length);
                textNode.textContent += fullText.slice(charIndex, end);
                charIndex = end;
                scrollToBottom();
            }, CHAR_DELAY);
        }, INITIAL_DELAY);
    }

    function showTypingIndicator() {
        const row = document.createElement('div');
        row.classList.add('typing-row');
        row.id = 'typingIndicator';
        row.innerHTML = `
            <div class="typing-inner">
                <div class="msg-avatar msg-avatar-bot">✦</div>
                <div class="typing-bubble">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        chatMessages.appendChild(row);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) indicator.remove();
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    function autoResizeTextarea() {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + 'px';
    }

    // Auto-resize on input
    chatInput.addEventListener('input', autoResizeTextarea);

    // ── Utilities ─────────────────────────────────────────────────────

    function generateSessionId() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
            const r = (Math.random() * 16) | 0;
            const v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }
})();
