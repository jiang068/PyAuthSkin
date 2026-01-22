/**
 * PyAuthSkin Global Script - Optimized for No-Flash PJAX
 */

// ... (toggleTheme 和 openDeleteModal 保持不变) ...

const pjaxContainerId = 'pjax-container';

// 核心改进：更新 DOM 的时候不再强制闪烁
async function updateDOM(html, url, pushState = true) {
    const pjaxContainer = document.getElementById(pjaxContainerId);
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const newContent = doc.getElementById(pjaxContainerId);
    
    if (newContent && pjaxContainer) {
        // 直接更新内容，不再这里处理 pjax-loading 类，避免视觉闪烁
        pjaxContainer.innerHTML = newContent.innerHTML;
        document.title = doc.title;
        
        if (pushState && url !== window.location.href) {
            window.history.pushState({ url }, doc.title, url);
        }
        // 移除加载状态
        pjaxContainer.classList.remove('pjax-loading');
    } else {
        window.location.href = url;
    }
}

async function loadPage(url, pushState = true) {
    const pjaxContainer = document.getElementById(pjaxContainerId);
    // 只有在加载新页面（GET）时，才在延迟后开启加载效果
    const timer = setTimeout(() => pjaxContainer?.classList.add('pjax-loading'), 300);
    
    try {
        const res = await fetch(url);
        clearTimeout(timer); // 如果请求很快，直接取消加载效果
        if (!res.ok) throw new Error('Network response was not ok');
        updateDOM(await res.text(), res.url, pushState);
    } catch (e) {
        clearTimeout(timer);
        window.location.href = url;
    }
}

// 拦截表单提交：完全移除“变暗”逻辑，实现无感刷新
document.addEventListener('submit', async e => {
    const f = e.target;
    const pjaxContainer = document.getElementById(pjaxContainerId);
    const actionUrl = new URL(f.action, window.location.origin);
    
    if (actionUrl.origin === window.location.origin) {
        e.preventDefault();
        
        // 注意：这里不再添加 pjax-loading，让用户感觉操作是瞬时的
        
        try {
            const formData = new FormData(f);
            let fetchOptions = {
                method: f.method.toUpperCase() || 'POST',
                body: formData
            };

            if (f.enctype !== 'multipart/form-data') {
                fetchOptions.body = new URLSearchParams(formData);
                fetchOptions.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
            }

            const res = await fetch(f.action, fetchOptions);
            if (res.ok) {
                const html = await res.text();
                // 执行更新，内容会瞬间替换，没有任何透明度变化
                updateDOM(html, res.url, false);
            } else {
                window.location.reload();
            }
        } catch (err) {
            window.location.reload();
        }
    }
});

// 监听链接点击
document.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (a && a.href && a.origin === window.location.origin) {
        // 排除退出登录和带下载属性的链接
        if (a.href.includes('/logout') || a.hasAttribute('download') || a.target) return;
        
        e.preventDefault();
        loadPage(a.href);
    }
});

// 监听浏览器后退/前进
window.onpopstate = () => loadPage(window.location.pathname, false);

// --- 核心改进：表单提交 PJAX 拦截 ---
document.addEventListener('submit', async e => {
    const f = e.target;
    const pjaxContainer = document.getElementById(pjaxContainerId);
    
    // 获取表单动作的完整 URL
    const actionUrl = new URL(f.action, window.location.origin);
    
    // 只处理同源表单
    if (actionUrl.origin === window.location.origin) {
        e.preventDefault(); // 阻止浏览器默认跳转
        
        if (pjaxContainer) pjaxContainer.classList.add('pjax-loading');

        try {
            const formData = new FormData(f);
            let fetchOptions = {
                method: f.method.toUpperCase() || 'POST',
                body: formData
            };

            // 如果不是文件上传，使用 URLSearchParams 以保持更好的后端兼容性
            if (f.enctype !== 'multipart/form-data') {
                fetchOptions.body = new URLSearchParams(formData);
                fetchOptions.headers = {
                    'Content-Type': 'application/x-www-form-urlencoded'
                };
            }
            // 注意：如果是 multipart/form-data，不要手动设 Content-Type，
            // 浏览器会自动生成包含 boundary 的 header。

            const res = await fetch(f.action, fetchOptions);
            
            if (res.ok) {
                const html = await res.text();
                // 使用 res.url 确保处理了后端可能的 redirect 重定向
                updateDOM(html, res.url, false); // 提交操作通常不产生新的历史记录
            } else {
                throw new Error('Form submission failed');
            }
        } catch (err) {
            console.error('PJAX Submit Error:', err);
            // 失败时回退到普通刷新，确保业务不中断
            f.submit();
        }
    }
});