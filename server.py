import socket
import threading
import time
import os
from datetime import datetime

class ChatServer:
    def __init__(self):
        # 服务器配置
        self.host = input("输入开放IP：")  # 服务器地址
        self.port = int(input("输入开放端口："))       # 服务器端口
        self.clients = {}      # 存储客户端连接: {client_socket: nickname}
        self.nicknames = set() # 存储已使用的昵称，防止重复
        self.chat_history = [] # 存储聊天历史记录
        self.server_desc = ""  # 服务器描述
        self.history_file = "chat_history.log"  # 聊天历史存储文件

        # 初始化：读取历史记录
        self.load_history()

        # 获取服务器描述（最多20字）
        self.get_server_description()

        # 创建TCP和UDP套接字
        self.create_sockets()

        # 启动服务器
        self.start_server()

    def load_history(self):
        if not os.path.exists(self.history_file):
            return False
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self.chat_history = [line.strip() for line in f if line.strip()]
            print(f"成功加载 {len(self.chat_history)} 条聊天历史记录")
        except Exception as e:
            print(f"加载历史记录失败: {e}")
            self.chat_history = []

    def save_chat_history(self):
        """关闭服务器时，将聊天历史记录保存到文件"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                for msg in self.chat_history:
                    if msg[0] == "[" and msg[1] == "历" and msg[2] == "史" and msg[3] == "记" and msg[4] == "录" and msg[5] == "]":
                        f.write(f"{msg}\n")
                    else:
                        f.write(f"[历史记录]{msg}\n")
            print(f"成功保存 {len(self.chat_history)} 条聊天历史记录到 {self.history_file}")
        except Exception as e:
            print(f"保存聊天历史失败: {e}")
            
    def get_server_description(self):
        """获取用户输入的服务器描述，限制最多20字"""
        while True:
            desc = input("请输入服务器描述（最多20字，按回车使用默认描述）：").strip()
            if len(desc) > 20:
                print("描述过长，请输入不超过20字的内容！")
            else:
                self.server_desc = desc if desc else "默认聊天室服务器"
                break

    def create_sockets(self):
        """创建TCP套接字（用于聊天）和UDP套接字（用于客户端扫描）"""
        # TCP套接字
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 端口复用

        # UDP套接字（用于响应客户端扫描）
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start_server(self):
        """启动服务器，绑定端口并启动监听"""
        try:
            # 绑定TCP和UDP端口
            self.tcp_socket.bind((self.host, self.port))
            self.udp_socket.bind((self.host, self.port))

            # TCP监听客户端连接
            self.tcp_socket.listen(5)
            print(f"=== 聊天室服务器启动成功 ===")
            print(f"服务器地址: {self.host}:{self.port}")
            print(f"服务器描述: {self.server_desc}")
            print(f"等待客户端连接...\n")

            # 启动UDP线程处理客户端扫描请求
            udp_thread = threading.Thread(target=self.handle_udp_probe, daemon=True)
            udp_thread.start()

            # 启动TCP线程接受客户端连接
            tcp_thread = threading.Thread(target=self.accept_clients, daemon=True)
            tcp_thread.start()

            # 保持主线程运行
            while True:
                command = input("输入 'quit' 关闭服务器：\n")
                if command.lower() == 'quit':
                    self.shutdown_server()
                    break

        except Exception as e:
            print(f"服务器启动失败: {e}")
            exit(1)

    def handle_udp_probe(self):
        """处理客户端的UDP扫描请求"""
        while True:
            try:
                # 接收客户端的探测数据
                data, addr = self.udp_socket.recvfrom(1024)
                if data.decode('utf-8') == "cs":  # 客户端探测标识
                    # 响应格式：sc|服务器描述
                    response = f"sc|{self.server_desc}"
                    self.udp_socket.sendto(response.encode('utf-8'), addr)
            except Exception as e:
                continue

    def accept_clients(self):
        """接受客户端的TCP连接"""
        while True:
            try:
                # 等待客户端连接
                client_socket, client_addr = self.tcp_socket.accept()
                print(f"新的连接请求: {client_addr}")

                # 启动线程处理客户端
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_addr), daemon=True)
                client_thread.start()

            except Exception as e:
                print(f"接受连接失败: {e}")
                break

    def handle_client(self, client_socket, client_addr):
        """处理单个客户端的交互"""
        nickname = None
        try:
            # 第一步：验证昵称
            while True:
                # 接收客户端发送的昵称
                nickname = client_socket.recv(1024).decode('utf-8').strip()
                if not nickname:
                    client_socket.send("NICK_EMPTY".encode('utf-8'))
                    continue
                if nickname in self.nicknames:
                    client_socket.send("NICK_EXISTS".encode('utf-8'))
                else:
                    # 昵称验证通过
                    self.nicknames.add(nickname)
                    self.clients[client_socket] = nickname
                    client_socket.send("NICK_OK".encode('utf-8'))
                    break

            print(f"客户端 {client_addr} 成功连接，昵称: {nickname}")

            # 发送欢迎消息和聊天历史
            welcome_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 系统: 欢迎 {nickname} 加入聊天室！"
            self.broadcast(welcome_msg, exclude=client_socket)
            
            time.sleep(0.5)
            # 发送历史记录
            for msg in self.chat_history:
                client_socket.send(msg.encode('utf-8'))
                time.sleep(0.01)
            client_socket.send("[历史记录end]".encode('utf-8'))

            # 第二步：处理客户端消息
            while True:
                # 接收客户端消息
                msg = client_socket.recv(1024).decode('utf-8')
                if not msg:
                    break

                # 处理退出指令
                if msg.lower() == 'quit':
                    break

                # 格式化消息
                full_msg = f"{msg}"
                
                # 保存到历史记录
                self.add_to_history(full_msg)
                
                # 广播消息
                self.broadcast(full_msg)

        except Exception as e:
            print(f"客户端 {client_addr} 通信出错: {e}")

        finally:
            # 清理客户端连接
            if client_socket in self.clients:
                self.nicknames.remove(self.clients[client_socket])
                del self.clients[client_socket]
                client_socket.close()
                leave_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 系统: {nickname} 离开聊天室！"
                self.broadcast(leave_msg)
                print(f"客户端 {client_addr} 已断开连接")

    def add_to_history(self, msg):
        """添加消息到历史记录，限制最大条数"""
        self.chat_history.append(msg)

    def broadcast(self, msg, exclude=None):
        """广播消息给所有客户端，可指定排除某个客户端"""
        for client_socket in list(self.clients.keys()):
            if client_socket != exclude:
                try:
                    client_socket.send(msg.encode('utf-8'))
                except:
                    # 发送失败则移除客户端
                    self.nicknames.remove(self.clients[client_socket])
                    del self.clients[client_socket]
                    client_socket.close()

    def shutdown_server(self):
        """关闭服务器"""
        print("\n正在关闭服务器...")
        # 关闭所有客户端连接
        self.save_chat_history()
        for client_socket in list(self.clients.keys()):
            try:
                client_socket.send("服务器即将关闭，连接将断开！".encode('utf-8'))
                client_socket.close()
            except:
                pass
        # 关闭套接字
        self.tcp_socket.close()
        self.udp_socket.close()
        print("服务器已成功关闭")
        exit(0)

if __name__ == "__main__":
    # 启动服务器

    ChatServer()
