/**
 * PyAuthSkin Global Script
 */

// 1. 全局配置与初始化
window.tailwind.config = { darkMode: 'class' };

window.toggleTheme = function() {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.theme = isDark ? 'dark' : 'light';
};

// 2. 模态框逻辑绑定全局
let formToSubmit = null;
window.openDeleteModal = function(formId) {
    formToSubmit = document.getElementById(formId);
    const modal = document.getElementById('delete-modal');
    const card = document.getElementById('modal-card');
    if (!modal || !card) return;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    requestAnimationFrame(() => card.classList.replace('scale-95', 'scale-100'));
    
    document.getElementById('confirm-delete-btn').onclick = () => {
        if (formToSubmit) {
            const event = new Event('submit', { cancelable: true, bubbles: true });
            formToSubmit.dispatchEvent(event);
            window.closeDeleteModal();
        }
    };
};

window.closeDeleteModal = function() {
    const modal = document.getElementById('delete-modal');
    const card = document.getElementById('modal-card');
    if (!modal || !card) return;
    card.classList.replace('scale-100', 'scale-95');
    setTimeout(() => {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }, 100);
};

// 3. PJAX 核心逻辑
const pjaxContainerId = 'pjax-container';

async function updateDOM(html, url, pushState = true) {
    const container = document.getElementById(pjaxContainerId);
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const newContent = doc.getElementById(pjaxContainerId);
    
    if (newContent && container) {
        container.innerHTML = newContent.innerHTML;
        document.title = doc.title;
        if (pushState && url !== window.location.href) {
            window.history.pushState({ url }, doc.title, url);
        }
        container.classList.remove('pjax-loading');
    } else {
        window.location.href = url;
    }
}

async function loadPage(url, pushState = true) {
    const container = document.getElementById(pjaxContainerId);
    // 只有请求超过 300ms 才会显示变暗动画，防止快速切换时的闪烁
    const timer = setTimeout(() => container?.classList.add('pjax-loading'), 300);
    
    try {
        const res = await fetch(url);
        clearTimeout(timer);
        if (!res.ok) throw new Error();
        updateDOM(await res.text(), res.url, pushState);
    } catch (e) {
        clearTimeout(timer);
        window.location.href = url;
    }
}

// 4. 事件监听器
document.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (a && a.href && a.origin === window.location.origin) {
        if (a.href.includes('/logout') || a.hasAttribute('download') || a.target) return;
        e.preventDefault();
        loadPage(a.href);
    }
});

window.onpopstate = () => loadPage(window.location.pathname, false);

document.addEventListener('submit', async e => {
    const f = e.target;
    const container = document.getElementById(pjaxContainerId);
    const actionUrl = new URL(f.action, window.location.origin);
    
    if (actionUrl.origin === window.location.origin) {
        e.preventDefault();
        // 提交时不添加 pjax-loading，实现“瞬时”感
        
        try {
            const formData = new FormData(f);
            let fetchOptions = { method: f.method.toUpperCase() || 'POST' };

            if (f.enctype === 'multipart/form-data') {
                fetchOptions.body = formData; // 文件上传
            } else {
                fetchOptions.body = new URLSearchParams(formData); // 普通表单
                fetchOptions.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
            }

            const res = await fetch(f.action, fetchOptions);
            const html = await res.text();
            updateDOM(html, res.url, false);
        } catch (err) {
            f.submit(); // 出错则退回到普通提交
        }
    }
});