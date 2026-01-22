/**
 * PyAuthSkin Global Script
 */

// 1. 初始化
window.tailwind.config = { darkMode: 'class' };

window.toggleTheme = function() {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.theme = isDark ? 'dark' : 'light';
};

// 2. 模态框
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
const navContentId = 'nav-content'; // 核心容器：导航栏

async function updateDOM(html, url, pushState = true) {
    const container = document.getElementById(pjaxContainerId);
    const currentNav = document.getElementById(navContentId);
    
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const newContent = doc.getElementById(pjaxContainerId);
    const newNav = doc.getElementById(navContentId);
    
    if (newContent && container) {
        // 关键点：每次更新页面时，同时同步导航栏内容
        if (newNav && currentNav) {
            currentNav.innerHTML = newNav.innerHTML;
        }

        container.innerHTML = newContent.innerHTML;
        document.title = doc.title;
        
        if (pushState && url !== window.location.href) {
            window.history.pushState({ url }, doc.title, url);
        }
        container.classList.remove('pjax-loading');
    } else {
        // 降级：如果 PJAX 失败，硬跳转
        window.location.href = url;
    }
}

async function loadPage(url, pushState = true) {
    const container = document.getElementById(pjaxContainerId);
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

// 4. 全局拦截
document.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (a && a.href && a.origin === window.location.origin) {
        // 排除退出登录，退出操作必须硬跳转以清理 Session
        if (a.href.includes('/logout') || a.hasAttribute('download') || a.target) return;
        e.preventDefault();
        loadPage(a.href);
    }
});

window.onpopstate = () => loadPage(window.location.pathname, false);

document.addEventListener('submit', async e => {
    const f = e.target;
    const actionUrl = new URL(f.action, window.location.origin);
    
    // 如果是同源表单提交
    if (actionUrl.origin === window.location.origin) {
        e.preventDefault();
        try {
            const formData = new FormData(f);
            let fetchOptions = { method: f.method.toUpperCase() || 'POST' };
            if (f.enctype === 'multipart/form-data') {
                fetchOptions.body = formData;
            } else {
                fetchOptions.body = new URLSearchParams(formData);
                fetchOptions.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
            }

            const res = await fetch(f.action, fetchOptions);
            const html = await res.text();
            // 提交成功后，通过 updateDOM 替换内容和导航栏
            updateDOM(html, res.url, true);
        } catch (err) {
            console.error("PJAX Error:", err);
            window.location.reload();
        }
    }
});