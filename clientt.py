import socket
import threading
from datetime import datetime
import time
import time
from queue import Queue
import tkinter as tk
from tkinter import messagebox


class ChatClientGUI:
    def __init__(self):
        self.server_ip = None
        self.nickname = None
        self.client = None
        self.scan_results = Queue()
        self.stop_scan = False
        self.found_servers = []  # 存储格式：(ip, desc)
        self.scanned_count = 0
        self.total_ips = 0
        self.current_frame = None  # 跟踪当前活动框架

        self.root = tk.Tk()
        self.root.title("聊天室客户端")

        # 创建初始框架
        self.current_frame = tk.Frame(self.root)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

        # 输入昵称
        self.nickname_label = tk.Label(self.current_frame, text="输入你的昵称:")
        self.nickname_label.pack()
        self.nickname_entry = tk.Entry(self.current_frame)
        self.nickname_entry.pack()
        self.nickname_button = tk.Button(self.current_frame, text="确认昵称", command=self.confirm_nickname)
        self.nickname_button.pack()

        # 绑定昵称输入框的Enter键
        self.nickname_entry.bind("<Return>", lambda event: self.confirm_nickname())

        self.root.mainloop()

    def confirm_nickname(self):
        self.nickname = self.nickname_entry.get()
        if not self.nickname:
            messagebox.showerror("错误", "昵称不能为空！")
            return
            
        # 安全地销毁当前框架
        self.current_frame.destroy()
        
        # 选择连接方式
        self.choose_connection_method()

    def choose_connection_method(self):
        # 创建新框架
        self.current_frame = tk.Frame(self.root)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.current_frame, text="请选择连接方式:").pack()
        
        # 创建按钮引用，以便后续绑定Enter键
        custom_button = tk.Button(self.current_frame, text="自动查找局域网服务器", 
                                command=lambda: self.custom_scan())
        custom_button.pack()
        
        manual_button = tk.Button(self.current_frame, text="手动输入服务器地址", 
                                command=lambda: self.manual_connect())
        manual_button.pack()

        # 绑定按钮的Enter键
        custom_button.bind("<Return>", lambda event: self.custom_scan())
        manual_button.bind("<Return>", lambda event: self.manual_connect())

    def custom_scan(self):
        # 销毁当前框架
        self.current_frame.destroy()
        
        # 创建新框架
        self.current_frame = tk.Frame(self.root)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.current_frame, text="输入IP范围 (例如: 192.168.*.* 或 192.168.3.*):").pack()
        ip_pattern_entry = tk.Entry(self.current_frame, width=30)
        ip_pattern_entry.pack()
        
        tk.Label(self.current_frame, text="输入端口 (0~65535):").pack()
        port_pattern_entry = tk.Entry(self.current_frame, width=7)
        port_pattern_entry.pack()

        scan_button = tk.Button(self.current_frame, text="开始扫描", 
                              command=lambda: self.start_custom_scan(ip_pattern_entry.get(), port_pattern_entry.get()))
        scan_button.pack()
        
        back_button = tk.Button(self.current_frame, text="返回", 
                             command=lambda: self.back_to_connection_method())
        back_button.pack()

        # 绑定输入框和按钮的Enter键
        ip_pattern_entry.bind("<Return>", lambda event: self.start_custom_scan(ip_pattern_entry.get(), port_pattern_entry.get()))
        port_pattern_entry.bind("<Return>", lambda event: self.start_custom_scan(ip_pattern_entry.get(), port_pattern_entry.get()))
        scan_button.bind("<Return>", lambda event: self.start_custom_scan(ip_pattern_entry.get(), port_pattern_entry.get()))
        back_button.bind("<Return>", lambda event: self.back_to_connection_method())

        # 设置焦点到输入框
        ip_pattern_entry.focus_set()

    def back_to_connection_method(self):
        # 销毁当前框架
        self.current_frame.destroy()
        self.choose_connection_method()

    def start_custom_scan(self, ip_pattern, port_pattern):
        # 验证IP模式
        if not self.validate_ip_pattern(ip_pattern):
            messagebox.showerror("错误", "无效的IP范围格式！请使用类似 192.168.*.* 或 192.168.3.* 的格式")
            return
        try:
            port_pattern = int(port_pattern)
        except ValueError:
            messagebox.showerror("错误", "无效的端口！端口号应只含有数字")
            return
        
        if port_pattern < 0 or port_pattern > 65535:
            messagebox.showerror("错误", "无效的端口！有效的端口范围为0~65535")
            return
        
        self.server_port = port_pattern

        # 解析IP模式
        ip_ranges = self.parse_ip_pattern(ip_pattern)
        if not ip_ranges:
            messagebox.showerror("错误", "无法解析IP范围！")
            return

        # 计算总IP数
        self.total_ips = 1
        for r in ip_ranges:
            self.total_ips *= len(r)

        # 清空当前框架
        for widget in self.current_frame.winfo_children():
            widget.destroy()

        tk.Label(self.current_frame, text=f"正在扫描IP范围: {ip_pattern}").pack()
        progress_label = tk.Label(self.current_frame, text="准备中...")
        progress_label.pack()

        # 重置扫描状态
        self.stop_scan = False
        self.found_servers = []  # 清空之前的扫描结果 (ip, desc)
        self.scanned_count = 0
        
        # 使用500个线程进行扫描
        threads = []
        thread_count = 500
        
        # 计算每个线程负责的IP数量
        total_ips = self.total_ips
        ips_per_thread = max(1, total_ips // thread_count)
        
        # 分配任务给每个线程
        for i in range(thread_count):
            start_ip = i * ips_per_thread
            end_ip = min((i + 1) * ips_per_thread, total_ips)
            
            if start_ip >= end_ip:
                continue
                
            t = threading.Thread(target=self.scan_ip_range_chunk, 
                                args=(ip_ranges, start_ip, end_ip))
            t.start()
            threads.append(t)

        # 显示进度
        def display_progress():
            start_time = time.time()
            while any(t.is_alive() for t in threads):
                time.sleep(0.05)

                # 计算进度
                if self.total_ips > 0:
                    percent = (self.scanned_count / self.total_ips) * 100
                    elapsed = time.time() - start_time
                    ips_per_sec = self.scanned_count / elapsed if elapsed > 0 else 0

                    progress_label.config(text=f"扫描进度: {percent:.1f}%({self.scanned_count}/{self.total_ips}) 速度: {ips_per_sec:.1f} IP/s")
                    self.root.update()

            # 扫描完成，显示结果
            self.show_server_list()

        threading.Thread(target=display_progress, daemon=True).start()

    def show_server_list(self):
        """显示扫描到的服务器列表供选择（包含描述）"""
        # 清空当前框架
        for widget in self.current_frame.winfo_children():
            widget.destroy()

        if not self.found_servers:
            tk.Label(self.current_frame, text="未找到任何服务器！").pack()
            back_button = tk.Button(self.current_frame, text="返回", 
                                 command=lambda: self.back_to_connection_method())
            back_button.pack()
            back_button.focus_set()
            return

        # 显示服务器列表
        tk.Label(self.current_frame, text="找到以下服务器，请选择:").pack()
        
        # 创建列表框显示服务器（IP+描述）
        server_listbox = tk.Listbox(self.current_frame, width=60, height=10)
        server_listbox.pack(pady=10)
        
        # 添加服务器到列表
        for i, (server_ip, desc) in enumerate(self.found_servers):
            display_text = f"{server_ip}:{self.server_port} | 描述：{desc if desc else '无描述'}"
            server_listbox.insert(i, display_text)
        
        # 双击或按Enter键选择
        def select_server(event=None):
            selected_index = server_listbox.curselection()
            if selected_index:
                selected = server_listbox.get(selected_index)
                self.server_ip = selected.split(':')[0]  # 提取IP
                self._on_server_found()
        
        server_listbox.bind("<Double-1>", select_server)
        server_listbox.bind("<Return>", select_server)
        
        # 选择按钮
        select_button = tk.Button(self.current_frame, text="选择服务器", command=select_server)
        select_button.pack(pady=5)
        
        # 重新扫描按钮
        rescan_button = tk.Button(self.current_frame, text="重新扫描", 
                             command=lambda: self.custom_scan())
        rescan_button.pack(pady=5)
        
        # 返回按钮
        back_button = tk.Button(self.current_frame, text="返回", 
                             command=lambda: self.back_to_connection_method())
        back_button.pack(pady=5)
        
        # 设置焦点
        server_listbox.focus_set()
        if self.found_servers:
            server_listbox.selection_set(0)

    def _on_server_found(self):
        if self.connect_server():
            # 销毁当前框架
            self.current_frame.destroy()
            self.setup_chat_gui()

    def validate_ip_pattern(self, pattern):
        # 验证IP模式是否符合格式
        parts = pattern.split('.')
        if len(parts) != 4:
            return False
            
        for part in parts:
            if part == '*':
                continue
            try:
                num = int(part)
                if 0 <= num <= 255:
                    continue
                else:
                    return False
            except ValueError:
                return False
                
        return True

    def parse_ip_pattern(self, pattern):
        # 解析IP模式为各个部分的范围
        parts = pattern.split('.')
        ranges = []
        
        for part in parts:
            if part == '*':
                ranges.append(list(range(0, 256)))  # 0-255
            else:
                try:
                    num = int(part)
                    ranges.append([num])
                except ValueError:
                    return None
                    
        return ranges

    def scan_ip_range_chunk(self, ip_ranges, start_ip, end_ip):
        # 扫描指定范围的IP
        current_ip = 0
        
        # 计算所有可能的IP组合
        for i in range(len(ip_ranges[0])):
            for j in range(len(ip_ranges[1])):
                for k in range(len(ip_ranges[2])):
                    for l in range(len(ip_ranges[3])):
                        # 只处理当前线程负责的IP范围
                        if current_ip >= start_ip and current_ip < end_ip:
                            if self.stop_scan:
                                return
                                
                            # 构建IP
                            ip = f"{ip_ranges[0][i]}.{ip_ranges[1][j]}.{ip_ranges[2][k]}.{ip_ranges[3][l]}"
                            
                            # 探测服务器并获取描述
                            probe_result = self.probe_server(ip)
                            if probe_result:
                                server_ip, server_desc = probe_result
                                # 确保服务器IP不重复添加
                                with threading.Lock():
                                    if server_ip not in [s[0] for s in self.found_servers]:
                                        self.found_servers.append((server_ip, server_desc))
                                
                            # 原子操作更新扫描计数
                            with threading.Lock():
                                self.scanned_count += 1
                                
                        current_ip += 1
                        
                        # 如果已经处理完分配的IP，退出循环
                        if current_ip >= end_ip:
                            return

    def scan_and_connect(self):
        # 销毁当前框架
        self.current_frame.destroy()
        
        # 创建新框架
        self.current_frame = tk.Frame(self.root)
        self.current_frame.pack(fill=tk.BOTH, expand=True)
        
        # 获取本地IP并构建默认扫描范围
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            network_prefix = '.'.join(local_ip.split('.')[:2])  # 192.168
            default_range = f"{network_prefix}.*.*"
        except:
            default_range = "192.168.*.*"

        tk.Label(self.current_frame, text=f"输入IP范围 (默认: {default_range}):").pack()
        ip_pattern_entry = tk.Entry(self.current_frame, width=30)
        ip_pattern_entry.insert(0, default_range)
        ip_pattern_entry.pack()
        
        scan_button = tk.Button(self.current_frame, text="开始扫描", 
                              command=lambda: self.start_custom_scan(ip_pattern_entry.get()))
        scan_button.pack()
        
        back_button = tk.Button(self.current_frame, text="返回", 
                             command=lambda: self.back_to_connection_method())
        back_button.pack()

        # 绑定输入框和按钮的Enter键
        ip_pattern_entry.bind("<Return>", lambda event: self.start_custom_scan(ip_pattern_entry.get()))
        scan_button.bind("<Return>", lambda event: self.start_custom_scan(ip_pattern_entry.get()))
        back_button.bind("<Return>", lambda event: self.back_to_connection_method())

        # 设置焦点到输入框
        ip_pattern_entry.focus_set()

    def manual_connect(self):
        # 销毁当前框架
        self.current_frame.destroy()

        # 创建新框架
        self.current_frame = tk.Frame(self.root)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.current_frame, text="输入服务端IP:").pack()
        ip_entry = tk.Entry(self.current_frame)
        ip_entry.pack()

        tk.Label(self.current_frame, text="输入服务端端口:").pack()
        port_entry = tk.Entry(self.current_frame)
        port_entry.pack()

        connect_button = tk.Button(self.current_frame, text="连接", 
                                 command=lambda: self._handle_connect(ip_entry, port_entry))
        connect_button.pack()

        # 绑定IP输入框的Enter键
        ip_entry.bind("<Return>", lambda event: self._handle_connect(ip_entry, port_entry))
        # 绑定端口输入框的Enter键
        port_entry.bind("<Return>", lambda event: self._handle_connect(ip_entry, port_entry))
        # 绑定连接按钮的Enter键
        connect_button.bind("<Return>", lambda event: self._handle_connect(ip_entry, port_entry))

        # 设置焦点到IP输入框
        ip_entry.focus_set()

    def _handle_connect(self, ip_entry, port_entry):
        self.server_ip = ip_entry.get()
        self.server_port = int(port_entry.get() or "5000")
        if self.connect_server():
            # 销毁当前框架
            self.current_frame.destroy()
            self.setup_chat_gui()

    def connect_server(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect((self.server_ip, self.server_port))
            self.client.sendall(self.nickname.encode('utf-8'))
            response = self.client.recv(1024).decode('utf-8')

            if response == "NICK_EXISTS":
                messagebox.showerror("错误", "昵称已存在！")
                self.nickname = input("重新输入你的昵称: ")
                return self.connect_server()

            messagebox.showinfo("成功", "连接服务器成功！")
            return True

        except Exception as e:
            messagebox.showerror("错误", f"连接失败: {e}")
            return False

    def receive_messages(self):
        while True:
            try:
                data = self.client.recv(1024).decode('utf-8')
                print(data)
                if data == "服务器即将关闭，连接将断开！":
                    time.sleep(1)
                    
                    # 安全地销毁当前框架
                    self.current_frame.destroy()
                    
                    # 选择连接方式
                    self.choose_connection_method()
                    break
                if not data:
                    messagebox.showinfo("提示", "与服务器断开连接")
                    break
                elif "[历史记录end]" in data:
                    pass
                else:
                    self.update_chat(data)
            except Exception as e:
                messagebox.showerror("错误", f"接收消息出错: {e}")
                break

    def update_chat(self, message):
        # 使用线程安全的方式更新UI
        self.root.after(0, lambda: self._update_chat_text(message))

    def _update_chat_text(self, message):
        # 保存当前滚动位置
        autoscroll = False
        if self.chat_text.yview()[1] >= 0.99:  # 如果用户在底部
            autoscroll = True

        self.chat_text.insert(tk.END, f"{message}\n")
        
        # 如果之前在底部，保持滚动到底部
        if autoscroll:
            self.chat_text.see(tk.END)

    def send_message(self, event=None):  # 支持event参数以处理Enter键
        msg = self.message_entry.get()
        if msg:
            if msg.lower() == 'quit':
                self.client.close()
                self.root.destroy()
            else:
                try:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    full_msg = f"[{timestamp}] {self.nickname}: {msg}"
                    self.client.sendall(full_msg.encode('utf-8'))
                    self.message_entry.delete(0, tk.END)
                except Exception as e:
                    messagebox.showerror("错误", f"发送失败: {e}")
        return "break"  # 阻止默认行为

    def setup_chat_gui(self):
        # 销毁当前框架
        if self.current_frame:
            self.current_frame.destroy()
            
        # 创建新框架
        self.current_frame = tk.Frame(self.root)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

        # 聊天显示区域
        self.chat_text = tk.Text(self.current_frame)
        self.chat_text.pack(fill=tk.BOTH, expand=True)

        # 消息输入框
        input_frame = tk.Frame(self.current_frame)
        input_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.message_entry = tk.Entry(input_frame, width=50)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        send_button = tk.Button(input_frame, text="发送", command=self.send_message)
        send_button.pack(side=tk.RIGHT)

        # 绑定Enter键到发送消息函数
        self.message_entry.bind("<Return>", self.send_message)
        # 绑定发送按钮的Enter键
        send_button.bind("<Return>", lambda event: self.send_message())

        # 设置焦点到消息输入框
        self.message_entry.focus_set()

        # 在聊天界面初始化后启动接收消息线程
        threading.Thread(target=self.receive_messages, daemon=True).start()
        
    def probe_server(self, ip):
        """探测服务器，返回 (ip, desc) 或 None"""
        try:
            probe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe_socket.settimeout(0.1)

            # 发送探测包
            probe_socket.sendto(b"cs", (ip, self.server_port))

            # 等待回复
            try:
                data, addr = probe_socket.recvfrom(1024)
                response = data.decode('utf-8')
                if response.startswith("sc|"):
                    # 提取描述（最多20字）
                    server_desc = response.split('|', 1)[1][:20]
                    return (ip, server_desc)
            except socket.timeout:
                pass
            finally:
                probe_socket.close()
        except Exception as e:
            pass
        return None

if __name__ == "__main__":
    ChatClientGUI()