# config.py

# 服务器监听的主机地址
# "127.0.0.1" 表示只有本机可以访问
# "0.0.0.0" 表示局域网内的其他机器也可以访问
HOST = "localhost"

# 服务器监听的端口
PORT = 80

# 完整的服务器基础 URL，用于生成皮肤链接
# 注意：如果你的服务器在公网，请将 HOST 替换为你的域名或公网 IP
BASE_URL = f"http://{HOST}" if PORT == 80 else f"http://{HOST}:{PORT}"
