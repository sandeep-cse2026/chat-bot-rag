/**
 * Entertainment & Books RAG Chatbot — Frontend Logic
 *
 * Handles:
 * - Session management (UUID-based)
 * - Message sending/receiving via POST /chat
 * - Typing indicator
 * - Markdown rendering (via marked.js)
 * - Auto-scroll to latest message
 * - Suggestion chip interaction
 * - Error display
 * - New chat / session clear
 */

(function () {
    'use strict';

    // ── DOM Elements ──────────────────────────────────────────────────
    const chatMessages = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const clearBtn = document.getElementById('clearBtn');
    const welcomeMessage = document.getElementById('welcomeMessage');

    // ── State ─────────────────────────────────────────────────────────
    let sessionId = generateSessionId();
    let isProcessing = false;

    // ── Marked.js Configuration ───────────────────────────────────────
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
            sanitize: false,
        });
    }

    // ── Event Listeners ───────────────────────────────────────────────
    chatForm.addEventListener('submit', handleSubmit);
    chatInput.addEventListener('input', handleInputChange);
    clearBtn.addEventListener('click', handleClearChat);

    // Suggestion chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const message = chip.getAttribute('data-message');
            if (message) {
                chatInput.value = message;
                handleInputChange();
                handleSubmit(new Event('submit'));
            }
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
        handleInputChange();

        // Show typing indicator and send
        showTypingIndicator();
        sendMessage(message);
    }

    function handleInputChange() {
        sendBtn.disabled = !chatInput.value.trim() || isProcessing;
    }

    async function handleClearChat() {
        // Clear on server
        try {
            await fetch('/chat/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId }),
            });
        } catch (e) {
            // Ignore errors
        }

        // Reset UI
        sessionId = generateSessionId();

        // Remove all messages except the welcome container
        const allMessages = chatMessages.querySelectorAll('.message, .typing-indicator');
        allMessages.forEach(msg => msg.remove());

        // Show welcome again
        if (welcomeMessage) {
            welcomeMessage.style.display = 'flex';
        }
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
                appendMessage('bot', data.response);
            } else {
                const errorMsg = data.error?.message || 'Something went wrong. Please try again.';
                appendMessage('error', errorMsg);
            }
        } catch (error) {
            hideTypingIndicator();
            appendMessage('error', 'Network error. Please check your connection and try again.');
        } finally {
            isProcessing = false;
            handleInputChange();
            chatInput.focus();
        }
    }

    // ── UI Helpers ────────────────────────────────────────────────────

    function appendMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', `message-${type}`);

        const avatar = document.createElement('div');
        avatar.classList.add('message-avatar');

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');

        if (type === 'user') {
            avatar.textContent = '👤';
            contentDiv.textContent = content;
        } else if (type === 'bot') {
            avatar.textContent = '✦';
            // Render markdown
            if (typeof marked !== 'undefined') {
                contentDiv.innerHTML = marked.parse(content);
            } else {
                contentDiv.textContent = content;
            }
        } else if (type === 'error') {
            avatar.textContent = '⚠️';
            contentDiv.textContent = content;
        }

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.classList.add('typing-indicator');
        indicator.id = 'typingIndicator';
        indicator.innerHTML = `
            <div class="message-avatar" style="background: linear-gradient(135deg, var(--bg-surface), var(--bg-tertiary)); border: 1px solid var(--glass-border);">✦</div>
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>
        `;
        chatMessages.appendChild(indicator);
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

    // ── Utilities ─────────────────────────────────────────────────────

    function generateSessionId() {
        // Generate UUID v4
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
            const r = (Math.random() * 16) | 0;
            const v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }
})();
