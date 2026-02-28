/**
 * EntertainBot — Synthwave Terminal Chat Logic
 *
 * Features:
 * - Session management (UUID-based)
 * - Streaming typing animation (terminal-style character reveal with block cursor)
 * - Markdown rendering (via marked.js)
 * - Auto-resize textarea
 * - Command card interaction
 * - Mobile sidebar toggle
 * - Smooth auto-scroll
 */

(function () {
    'use strict';

    // ── DOM ───────────────────────────────────────────────────────────
    const chatFeed = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const clearBtn = document.getElementById('clearBtn');
    const clearBtnMobile = document.getElementById('clearBtnMobile');
    const welcomeMessage = document.getElementById('welcomeMessage');
    const menuBtn = document.getElementById('menuBtn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    // ── State ─────────────────────────────────────────────────────────
    let sessionId = genId();
    let isProcessing = false;

    // ── Streaming config ──────────────────────────────────────────────
    const CHAR_DELAY = 6;
    const CHUNK_SIZE = 3;
    const INITIAL_DELAY = 80;

    // ── Marked setup ──────────────────────────────────────────────────
    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true, gfm: true });
    }

    // ── Events ────────────────────────────────────────────────────────
    chatForm.addEventListener('submit', onSubmit);
    chatInput.addEventListener('input', onInputChange);
    chatInput.addEventListener('input', autoResize);
    chatInput.addEventListener('keydown', onKeydown);
    clearBtn.addEventListener('click', onClear);
    if (clearBtnMobile) clearBtnMobile.addEventListener('click', onClear);

    if (menuBtn) {
        menuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        });
    }
    if (overlay) {
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });
    }

    // Command cards
    document.querySelectorAll('.cmd-card').forEach(card => {
        card.addEventListener('click', () => {
            const msg = card.getAttribute('data-message');
            if (msg) {
                chatInput.value = msg;
                autoResize();
                onInputChange();
                onSubmit(new Event('submit'));
            }
        });
    });

    // Module nav items
    document.querySelectorAll('.module-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.module-item').forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });
    });

    // ── Handlers ──────────────────────────────────────────────────────

    function onSubmit(e) {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg || isProcessing) return;

        if (welcomeMessage) welcomeMessage.style.display = 'none';

        addMessage('user', msg);
        chatInput.value = '';
        autoResize();
        onInputChange();
        showThinking();
        sendToServer(msg);
    }

    function onInputChange() {
        sendBtn.disabled = !chatInput.value.trim() || isProcessing;
    }

    function onKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSubmit(new Event('submit'));
        }
    }

    async function onClear() {
        try {
            await fetch('/chat/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId }),
            });
        } catch (_) { /* ignore */ }

        sessionId = genId();
        chatFeed.querySelectorAll('.msg-row, .thinking-row').forEach(el => el.remove());
        if (welcomeMessage) welcomeMessage.style.display = 'flex';
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
    }

    // ── API ───────────────────────────────────────────────────────────

    async function sendToServer(message) {
        isProcessing = true;
        onInputChange();

        try {
            const res = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, session_id: sessionId }),
            });

            const data = await res.json();
            hideThinking();

            if (data.success) {
                sessionId = data.session_id || sessionId;
                addMessageStreaming(data.response);
            } else {
                addMessage('error', data.error?.message || 'Something went wrong.');
                isProcessing = false;
                onInputChange();
                chatInput.focus();
            }
        } catch (_) {
            hideThinking();
            addMessage('error', 'Network error. Check your connection.');
            isProcessing = false;
            onInputChange();
            chatInput.focus();
        }
    }

    // ── Message builders ──────────────────────────────────────────────

    function addMessage(type, content) {
        const row = el('div', ['msg-row', `msg-row-${type}`]);
        if (type === 'error') row.classList.add('msg-error');

        const inner = el('div', ['msg-inner']);
        const avatar = el('div', ['msg-avatar']);
        const body = el('div', ['msg-body']);
        const label = el('div', ['msg-label']);
        const text = el('div', ['msg-text']);

        if (type === 'user') {
            avatar.classList.add('msg-avatar-user');
            avatar.textContent = '>';
            label.textContent = 'USER';
            text.textContent = content;
        } else if (type === 'bot') {
            avatar.classList.add('msg-avatar-bot');
            avatar.textContent = '>_';
            label.textContent = 'BOT';
            text.innerHTML = typeof marked !== 'undefined' ? marked.parse(content) : content;
        } else if (type === 'error') {
            avatar.classList.add('msg-avatar-bot');
            avatar.textContent = '!';
            label.textContent = 'ERR';
            text.textContent = content;
        }

        body.append(label, text);
        inner.append(avatar, body);
        row.appendChild(inner);
        chatFeed.appendChild(row);
        scrollDown();
    }

    function addMessageStreaming(content) {
        const row = el('div', ['msg-row', 'msg-row-bot']);
        const inner = el('div', ['msg-inner']);
        const avatar = el('div', ['msg-avatar', 'msg-avatar-bot']);
        avatar.textContent = '>_';

        const body = el('div', ['msg-body']);
        const label = el('div', ['msg-label']);
        label.textContent = 'BOT';

        const text = el('div', ['msg-text']);
        const cursor = el('span', ['stream-cursor']);

        body.append(label, text);
        text.appendChild(cursor);
        inner.append(avatar, body);
        row.appendChild(inner);
        chatFeed.appendChild(row);
        scrollDown();

        streamChars(text, cursor, content);
    }

    function streamChars(container, cursor, fullText) {
        let i = 0;
        const node = document.createTextNode('');
        container.insertBefore(node, cursor);

        setTimeout(() => {
            const iv = setInterval(() => {
                if (i >= fullText.length) {
                    clearInterval(iv);
                    cursor.remove();
                    container.innerHTML = typeof marked !== 'undefined' ? marked.parse(fullText) : fullText;
                    isProcessing = false;
                    onInputChange();
                    chatInput.focus();
                    scrollDown();
                    return;
                }
                const end = Math.min(i + CHUNK_SIZE, fullText.length);
                node.textContent += fullText.slice(i, end);
                i = end;
                scrollDown();
            }, CHAR_DELAY);
        }, INITIAL_DELAY);
    }

    // ── Thinking indicator ────────────────────────────────────────────

    function showThinking() {
        const row = el('div', ['thinking-row']);
        row.id = 'thinkingIndicator';
        row.innerHTML = `
            <div class="thinking-inner">
                <div class="msg-avatar msg-avatar-bot">>_</div>
                <div class="thinking-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>`;
        chatFeed.appendChild(row);
        scrollDown();
    }

    function hideThinking() {
        const el = document.getElementById('thinkingIndicator');
        if (el) el.remove();
    }

    // ── Utilities ─────────────────────────────────────────────────────

    function scrollDown() {
        requestAnimationFrame(() => { chatFeed.scrollTop = chatFeed.scrollHeight; });
    }

    function autoResize() {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    }

    function el(tag, classes) {
        const e = document.createElement(tag);
        if (classes) classes.forEach(c => e.classList.add(c));
        return e;
    }

    function genId() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
            const r = (Math.random() * 16) | 0;
            return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
        });
    }
})();
