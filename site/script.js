
/**
 * PyAuthSkin Global Script
 */

// 主题切换逻辑
function toggleTheme() {
    document.documentElement.classList.toggle('dark');
    localStorage.theme = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

// 皮肤管理：文件选择反馈
function handleFileSelect(input) {
    const zone = document.getElementById('upload-zone');
    const text = document.getElementById('upload-text');
    const subtext = document.getElementById('upload-subtext');
    const icon = document.getElementById('upload-icon');
    
    if (input && input.files && input.files[0]) {
        const fileName = input.files[0].name;
        text.innerText = fileName;
        text.classList.replace('text-slate-400', 'text-emerald-500');
        text.classList.add('font-bold');
        subtext.innerText = "Ready to upload";
        zone.classList.replace('border-slate-200', 'border-emerald-500');
        zone.classList.add('bg-emerald-50/10');
        icon.innerHTML = `<svg class="w-10 h-10 text-emerald-500 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>`;
    }
}

// 皮肤管理：自定义删除模态框逻辑
let formToSubmit = null;
function openDeleteModal(formId) {
    formToSubmit = document.getElementById(formId);
    const modal = document.getElementById('delete-modal');
    const card = document.getElementById('modal-card');
    
    if (!modal || !card) return;

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    requestAnimationFrame(() => {
        card.classList.replace('scale-95', 'scale-100');
    });
    
    document.getElementById('confirm-delete-btn').onclick = () => {
        if (formToSubmit) {
            // 触发表单提交（支持 PJAX 逻辑）
            const event = new Event('submit', { cancelable: true, bubbles: true });
            formToSubmit.dispatchEvent(event);
            if (!event.defaultPrevented) {
                formToSubmit.submit();
            }
            closeDeleteModal();
        }
    };
}

function closeDeleteModal() {
    const modal = document.getElementById('delete-modal');
    const card = document.getElementById('modal-card');
    if (!modal || !card) return;

    card.classList.replace('scale-100', 'scale-95');
    setTimeout(() => {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }, 100);
}

// PJAX 核心逻辑
const pjaxContainerId = 'pjax-container';

async function updateDOM(html, url, pushState = true) {
    const pjaxContainer = document.getElementById(pjaxContainerId);
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const newContent = doc.getElementById(pjaxContainerId);
    
    if (newContent && pjaxContainer) {
        pjaxContainer.classList.add('pjax-loading');
        requestAnimationFrame(() => {
            pjaxContainer.innerHTML = newContent.innerHTML;
            document.title = doc.title;
            if (pushState) window.history.pushState({ url }, doc.title, url);
            requestAnimationFrame(() => {
                pjaxContainer.classList.remove('pjax-loading');
            });
        });
    } else {
        window.location.href = url;
    }
}

async function loadPage(url, pushState = true) {
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Network response was not ok');
        updateDOM(await res.text(), res.url, pushState);
    } catch (e) {
        window.location.href = url;
    }
}

// 初始化全局事件监听
document.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (a && a.href && a.origin === window.location.origin && !a.hasAttribute('download') && !a.target && !a.href.includes('/logout')) {
        e.preventDefault();
        loadPage(a.href);
    }
});

window.onpopstate = () => loadPage(window.location.pathname, false);

document.addEventListener('submit', async e => {
    const f = e.target;
    const pjaxContainer = document.getElementById(pjaxContainerId);
    
    // 只拦截非文件上传的同源表单
    if (f.origin === window.location.origin && f.enctype !== 'multipart/form-data') {
        e.preventDefault();
        if (pjaxContainer) pjaxContainer.classList.add('pjax-loading');
        try {
            const res = await fetch(f.action, {
                method: f.method,
                body: new URLSearchParams(new FormData(f)),
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
            });
            const html = await res.text();
            updateDOM(html, res.url, true);
        } catch (err) {
            window.location.reload();
        }
    }
});
