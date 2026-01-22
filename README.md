![PyAuthSkin Banner](site/banner_pic.jpg)

**PyAuthSkin** 是一个轻量级、高性能的 Minecraft 登录验证器和皮肤站项目，完全由 Python 编写。它支持 Yggdrasil 认证协议，允许玩家使用自定义皮肤登录游戏。

---
### 功能特性

-   **Yggdrasil 认证**：兼容 `authlib-injector` 等第三方启动器。
-   **用户管理**：网页端注册、登录、登出，支持密码强度验证。
-   **皮肤管理**：用户可上传、切换、删除自己的皮肤，支持 Steve (经典) 和 Alex (纤细) 模型。
-   **多分辨率皮肤**：支持 64x64、128x128、512x512 等多种分辨率皮肤的上传和头像预览。
-   **可配置**：通过 `config.py` 轻松定制服务器行为和日志等级。
---

### 部署步骤

1.  **克隆项目**：
    ```bash
    git clone https://github.com/jiang068/PyAuthSkin.git
    cd PyAuthSkin
    ```

2.  **创建并激活虚拟环境**：
    ```bash
    python -m venv plavenv
    # Windows PowerShell
    .\plavenv\Scripts\Activate.ps1
    # Linux/macOS Bash
    # source plavenv/bin/activate
    ```

3.  **安装依赖**：
    ```bash
    pip install -r requirements.txt
    ```

4.  **启动项目**：
    ```bash
    python main.py
    ```
    项目将在 `http://127.0.0.1:80` 运行。
    **重要提示**：Minecraft 客户端（通过 `authlib-injector`）在加载皮肤时，要求皮肤 URL **不能包含端口号**。  
    因此，服务器必须监听在标准的 HTTP 端口 `80`，或者通过 **Nginx 等反向代理**将 `80` 端口的请求转发到你的应用端口。

---
### 配置说明 (`config.py`)

`config.py` 文件允许你定制服务器的行为：

-   `HOST`: 服务器监听的主机地址。默认为 `"127.0.0.1"`。
    -   `"127.0.0.1"`: 仅本机可访问。
    -   `"0.0.0.0"`: 局域网内其他机器也可访问。
-   `PORT`: 服务器监听的端口。默认为 `80`。
-   `AUTH_API_PREFIX`: Yggdrasil 认证 API 的自定义前缀。默认为 `"/api/pyauthskin"`。
    -   **重要**：如果你修改此项，请务必同步更新 `authlib-injector` 的配置。
-   `LOG_LEVEL`: Uvicorn 和应用的日志输出等级。默认为 `"info"`。
    -   可选值：`"debug"`, `"info"`, `"warning"`, `"error"`, `"critical"`。

---

### 服务器接入

#### 1. 配置 authlib-injector
**下载 authlib-injector**
前往 [authlib-injector Releases](https://github.com/yushijinhun/authlib-injector/releases) 下载 Jar 包并存放在服务器根目录。

**添加启动参数**
在服务器启动命令中加入以下参数（注意：`-javaagent` 必须位于 `-jar` 之前）：
```bash
-javaagent:"authlib-injector-1.2.7.jar"=http://127.0.0.1（域名）/api/pyauthskin
```

* **完整命令示例：**
```bash
java -Xmx2G -Xms2G -javaagent:"authlib-injector-1.2.7.jar"=http://127.0.0.1（域名）/api/pyauthskin -jar "fabric-server-mc.1.21.10-loader.0.17.3-launcher.1.1.0.jar" nogui
```

* **参数执行逻辑：**
$$\text{Java路径} \rightarrow \text{内存参数} \rightarrow \text{JavaAgent(注入器)} \rightarrow \text{核心文件(-jar)} \rightarrow \text{游戏参数(nogui)}$$

#### 2. 配置 server.properties
修改服务器目录下的 server.properties 文件：
```
online-mode=true（必须为 true。必须开启正版验证模式，authlib-injector 才能正常接管验证）  
enforce-secure-profile=false（建议关闭。防止因自定义验证服务器的签名校验问题导致无法连接）
```
---

### 玩家（客户端）接入
**以 PCL2 为例**  
在启动器中找到 `版本设置` -> `设置` -> `服务器`。  
| 配置项目 | 设置内容 |
| :--- | :--- |
| **登录方式** | `第三方登录：Authlib Injector 或 LittleSkin` |
| **认证服务器 (必填)** | `http://127.0.0.1（域名）/api/pyauthskin（确保 API 路径正确）` |
| **注册链接** | `http://127.0.0.1（域名）/register` |
| **服务器名称** | `随意填写` |
---
