#!/usr/bin/env python3
"""
Hermit Crab Agent - 寄居蟹自动迁移系统主程序
"""

import os
import sys
import argparse
import time
from datetime import datetime

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules import (
    Logger, get_config, get_current_ip,
    Monitor, Scanner, Migrator, Initializer,
    GitHubSync, CloudFlareAPI, ResendNotifier, get_ssh_password
)


class HermitCrabAgent:
    """Hermit Crab主控制器"""
    
    def __init__(self):
        """
        初始化Agent
        
        配置从环境变量（.env文件）读取
        """
        # 加载配置
        self.config = get_config()
        
        # 设置日志
        log_file = os.path.join(
            self.config['base']['install_path'],
            'logs',
            'hermit_crab.log'
        )
        logger_instance = Logger()
        logger_instance.setup(
            log_level=self.config['base']['log_level'],
            log_file=log_file
        )
        self.logger = logger_instance.get_logger()
        
        # 初始化模块
        self.monitor = Monitor(self.config)
        self.scanner = Scanner(self.config)
        self.migrator = Migrator(self.config)
        self.initializer = Initializer(self.config)
        self.github = GitHubSync(self.config)
        self.cloudflare = CloudFlareAPI(self.config)
        self.notifier = ResendNotifier(self.config)

        self.logger.info("Hermit Crab Agent 已启动")

        # 显示通知状态
        if self.notifier.is_available():
            self.logger.info(f"✅ 邮件通知已启用 -> {', '.join(self.config['notification']['to_emails'])}")
        else:
            self.logger.debug("邮件通知未启用")
    
    def cmd_init(self):
        """
        初始化生命周期

        系统会自动：
        - 记录当前时间戳作为添加日期
        - 从 config.yaml 读取 current_domain
        """
        self.logger.info("=" * 60)
        self.logger.info("初始化 Hermit Crab")
        self.logger.info("=" * 60)

        # 初始化生命周期（系统自动记录当前时间）
        lifecycle = self.monitor.initialize_lifecycle()

        # 显示当前域名（从配置读取）
        current_domain = self.config['base']['current_domain']
        self.logger.info(f"业务域名: {current_domain}")

        self.logger.info("✅ 初始化完成")
        self.monitor.display_status()

    def cmd_update_lifecycle(self, target_server_ip: str = None, old_lifecycle_json: str = None, old_lifecycle_base64: str = None):
        """
        迁移后更新生命周期（保留迁移历史）

        Args:
            target_server_ip: 当前服务器IP（用于查找服务器信息）
            old_lifecycle_json: 源服务器的lifecycle.json内容（JSON字符串）
            old_lifecycle_base64: 源服务器的lifecycle.json内容（base64编码）
        """
        self.logger.info("=" * 60)
        self.logger.info("更新生命周期（保留迁移历史）")
        self.logger.info("=" * 60)

        # 获取当前IP
        current_ip = get_current_ip()
        self.logger.info(f"当前服务器IP: {current_ip}")

        # 从GitHub或本地获取服务器信息
        if self.github.is_available():
            self.logger.info("从GitHub同步服务器列表...")
            nodes_data = self.github.pull_nodes()
            if nodes_data:
                self.scanner.save_nodes(nodes_data)

        # 查找当前服务器信息
        nodes_data = self.scanner.load_nodes()
        target_server = None
        for server in nodes_data.get('servers', []):
            if server.get('ip') == current_ip:
                target_server = server
                break

        if not target_server:
            self.logger.error(f"❌ 未找到当前服务器信息: {current_ip}")
            return False

        # 解析旧的lifecycle
        old_lifecycle = None

        # 优先使用base64编码的参数
        if old_lifecycle_base64:
            import base64
            import json
            try:
                decoded_json = base64.b64decode(old_lifecycle_base64).decode('utf-8')
                old_lifecycle = json.loads(decoded_json)
                self.logger.info(f"成功解码base64 lifecycle数据")
            except Exception as e:
                self.logger.warning(f"解码base64 lifecycle失败: {e}")
        elif old_lifecycle_json:
            import json
            try:
                old_lifecycle = json.loads(old_lifecycle_json)
            except Exception as e:
                self.logger.warning(f"解析旧lifecycle失败: {e}")

        # 更新生命周期
        self.monitor.update_lifecycle_for_migration(target_server, old_lifecycle)

        self.logger.info("✅ 生命周期更新完成")
        self.monitor.display_status()
        return True
    
    def cmd_status(self):
        """显示当前状态"""
        self.monitor.display_status()

        # 显示自动迁移状态
        import subprocess
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "hermit-crab-daemon.service"],
                capture_output=True, text=True, check=False
            )
            is_active = result.stdout.strip() == "active"

            self.logger.info("=" * 60)
            self.logger.info("自动迁移状态")
            self.logger.info("=" * 60)
            if is_active:
                self.logger.info("状态: ✅ 已启动")
                self.logger.info("说明: 系统将自动监控并在需要时执行迁移")
            else:
                self.logger.info("状态: ❌ 未启动")
                self.logger.info("说明: 需要手动执行迁移")
                self.logger.info("提示: 使用 'hermit-crab start' 启动自动迁移")
            self.logger.info("=" * 60)
        except Exception as e:
            self.logger.debug(f"无法检查daemon状态: {e}")

        # 如果启用了GitHub，显示服务器列表
        if self.github.is_available():
            self.logger.info("\n正在从GitHub同步服务器列表...")
            nodes_data = self.github.pull_nodes()
            if nodes_data:
                # 保存到本地
                self.scanner.save_nodes(nodes_data)

        self.logger.info("\n可用服务器列表:")
        self.scanner.list_servers()
    
    def cmd_check(self):
        """
        检查是否需要迁移
        """
        self.logger.info("=" * 60)
        self.logger.info("执行迁移检查")
        self.logger.info("=" * 60)

        # 检查生命周期
        status = self.monitor.get_status()

        if not status['initialized']:
            self.logger.error("❌ 生命周期未初始化，请先运行: agent.py init")
            return False

        self.logger.info(f"当前服务器剩余: {status['remaining_days']} 天")

        if not status['should_migrate']:
            self.logger.info("✅ 暂不需要迁移")
            return False

        self.logger.warning("🚨 需要执行迁移！")

        # 检查可用服务器数量
        available_servers = self.scanner.get_available_servers()
        available_count = len(available_servers)
        self.logger.info(f"当前可用备用服务器数量: {available_count} 台")

        # 发送生命周期警告通知（包含可用服务器数量）
        current_ip = get_current_ip()
        self.notifier.notify_lifecycle_warning(
            server_ip=current_ip,
            remaining_days=status['remaining_days'],
            total_days=self.config['lifecycle']['total_days'],
            domain=self.config['base']['current_domain'],
            available_servers_count=available_count
        )

        return True
    
    def cmd_migrate(self, target_ip: str = None, password: str = None, auto: bool = False, force: bool = False):
        """
        执行迁移

        Args:
            target_ip: 目标服务器IP（可选，自动选择）
            password: SSH密码（可选，从环境变量读取）
            auto: 是否自动模式（自动选择目标）
            force: 强制迁移（忽略生命周期检查，选择剩余时间最长的服务器）
        """
        # 创建独立的迁移日志
        from datetime import datetime
        import logging

        migration_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        migration_log_dir = os.path.join(
            self.config['base']['install_path'],
            'logs',
            'migrations'
        )
        os.makedirs(migration_log_dir, exist_ok=True)

        migration_log_file = os.path.join(
            migration_log_dir,
            f'migration_{migration_time}.log'
        )

        # 添加文件日志处理器
        file_handler = logging.FileHandler(migration_log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        try:
            self.logger.info("=" * 60)
            self.logger.info("开始执行迁移流程")
            self.logger.info(f"迁移日志: {migration_log_file}")
            self.logger.info("=" * 60)

            # 1. 检查是否需要迁移
            status = self.monitor.get_status()

            if not status['initialized']:
                self.logger.error("❌ 生命周期未初始化")
                return False

            current_remaining = status['remaining_days']
            current_ip = get_current_ip()
            self.logger.info(f"当前服务器IP: {current_ip}")
            self.logger.info(f"当前服务器剩余: {current_remaining} 天")

            # 如果是强制迁移，跳过生命周期检查
            if force:
                self.logger.warning("⚠️  强制迁移模式：忽略生命周期检查")

            # 2. 同步服务器列表
            if self.github.is_available():
                self.logger.info("从GitHub同步服务器列表...")
                nodes_data = self.github.pull_nodes()
                if nodes_data:
                    self.scanner.save_nodes(nodes_data)

            # 3. 选择目标服务器
            if target_ip is None:
                if not auto:
                    self.logger.error("请指定目标IP或使用 --auto 自动选择")
                    return False

                self.logger.info("自动选择目标服务器...")

                # 如果是强制模式，选择剩余时间最长的服务器
                if force:
                    target_server = self.scanner.select_longest_remaining_server()
                else:
                    target_server = self.scanner.select_target_server(current_remaining)

                if target_server is None:
                    self.logger.error("❌ 没有合适的目标服务器")

                    # 发送无可用服务器通知
                    self.notifier.notify_no_available_servers(
                        current_ip=current_ip,
                        remaining_days=current_remaining
                    )

                    return False

                target_ip = target_server['ip']
            else:
                # 手动指定IP，查找对应服务器信息
                available = self.scanner.get_available_servers()
                target_server = None

                for server in available:
                    if server['ip'] == target_ip:
                        target_server = server
                        break

                if target_server is None:
                    self.logger.error(f"❌ 目标服务器不在可用列表中: {target_ip}")
                    return False

            self.logger.info(f"目标服务器IP: {target_ip}")
            self.logger.info(f"目标剩余时间: {target_server['remaining_days']} 天")

            # 4. 获取SSH密码
            if password is None:
                # 从环境变量获取密码
                password = get_ssh_password(target_ip)

                if password is None:
                    self.logger.error(
                        "❌ 未找到SSH密码。请通过以下方式之一提供密码：\n"
                        "  1. 命令行参数：--password your_password\n"
                        "  2. 环境变量：HERMIT_SSH_PASSWORD=your_password\n"
                        "  3. .env 文件：HERMIT_SSH_PASSWORD=your_password"
                    )
                    return False
                else:
                    self.logger.info("✅ 已从环境变量获取SSH密码")
            else:
                self.logger.info("✅ 使用命令行提供的SSH密码")

            # 5. 获取锁（防止并发）
            if self.github.is_available():
                self.logger.info(f"尝试获取服务器锁: {target_ip}")

                if not self.github.acquire_lock(target_ip, current_ip):
                    self.logger.error("❌ 无法获取服务器锁，可能已被其他服务器选中")
                    return False
            else:
                # 本地更新状态
                self.scanner.update_server_status(target_ip, 'transferring')

            # 6. 执行迁移
            migrate_start_time = datetime.now()
            self.logger.info(f"迁移开始时间: {migrate_start_time.strftime('%Y-%m-%d %H:%M:%S')}")

            # 发送迁移开始通知
            self.notifier.notify_migration_started(
                source_ip=current_ip,
                target_ip=target_ip,
                remaining_days=current_remaining
            )

            if not self.migrator.perform_migration(target_ip, password):
                self.logger.error("❌ 迁移失败")

                # 发送迁移失败通知
                self.notifier.notify_migration_failed(
                    source_ip=current_ip,
                    target_ip=target_ip,
                    error_message="Rsync 迁移失败，请查看日志了解详情",
                    stage="数据传输"
                )

                # 释放锁
                if self.github.is_available():
                    self.github.release_lock(target_ip, 'idle')
                return False

            # 7. 记录迁移历史（在初始化目标服务器之前，这样可以传递迁移历史）
            self.monitor.add_migration_record(target_server)

            # 8. 初始化目标服务器
            init_success = self.initializer.initialize_target_server(target_ip, target_server, self.migrator)
            if not init_success:
                self.logger.error("❌ 目标服务器初始化失败")
                # 但 Rsync 已经成功，标记为部分成功
                self.logger.warning("⚠️  迁移主体完成但初始化失败，需要手动完成初始化")

            # 9. 更新DNS（如果启用）
            if self.cloudflare.is_available():
                current_subdomain = self.config['base']['current_domain'].split('.')[0]

                # 更新主域名到新服务器
                self.logger.info(f"更新主域名DNS: {current_subdomain} -> {target_ip}")
                if self.cloudflare.update_domain_for_migration(current_subdomain, target_ip):
                    self.logger.info("✅ 主域名DNS已更新")
                else:
                    self.logger.warning("⚠️  主域名DNS更新失败，可能需要手动更新")

                # 将旧服务器IP解析到备用域名 b.ssfxx.com
                self.logger.info(f"更新旧服务器到备用域名: b -> {current_ip}")
                if self.cloudflare.update_dns_record('b', current_ip):
                    self.logger.info("✅ 旧服务器已解析到 b.ssfxx.com")
                else:
                    self.logger.warning("⚠️  备用域名更新失败")

            # 9. 更新服务器状态（即使初始化失败也要更新）
            self.logger.info("更新服务器状态...")

            if self.github.is_available():
                # 目标服务器设置为 active
                self.github.update_server_status(target_ip, 'active')

                # 删除源服务器（已废弃）
                self.logger.info(f"删除源服务器: {current_ip}")
                nodes_data = self.github.pull_nodes()
                if nodes_data:
                    servers = nodes_data.get('servers', [])
                    servers = [s for s in servers if s.get('ip') != current_ip]
                    nodes_data['servers'] = servers
                    self.github.push_nodes(nodes_data, f"Remove retired server {current_ip}")
            else:
                # 目标服务器设置为 active
                self.scanner.update_server_status(target_ip, 'active')

                # 删除源服务器
                nodes_data = self.scanner.load_nodes()
                servers = nodes_data.get('servers', [])
                servers = [s for s in servers if s.get('ip') != current_ip]
                nodes_data['servers'] = servers
                self.scanner.save_nodes(nodes_data)

            # 10. 再次增量同步最新的日志和数据到新服务器（保留完整迁移历史）
            self.logger.info("=" * 60)
            self.logger.info("同步最新日志和数据到新服务器...")
            self.logger.info("=" * 60)

            if self.migrator.sync_final_updates(target_ip, password):
                self.logger.info("✅ 最新日志和数据已同步到新服务器")
            else:
                self.logger.warning("⚠️  最终同步失败，部分日志可能未同步")

            # 计算总耗时
            migrate_end_time = datetime.now()
            total_elapsed = (migrate_end_time - migrate_start_time).total_seconds()

            # 发送迁移成功通知
            self.notifier.notify_migration_success(
                source_ip=current_ip,
                target_ip=target_ip,
                duration_seconds=total_elapsed,
                domain=self.config['base']['current_domain']
            )

            self.logger.info("=" * 60)
            self.logger.info("🎉 迁移流程全部完成！")
            self.logger.info("=" * 60)
            self.logger.info(f"源服务器IP: {current_ip}")
            self.logger.info(f"目标服务器IP: {target_ip}")
            self.logger.info(f"迁移开始时间: {migrate_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"迁移结束时间: {migrate_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"总耗时: {total_elapsed:.2f}秒 ({total_elapsed/60:.1f}分钟)")
            self.logger.info(f"迁移日志已保存: {migration_log_file}")
            self.logger.info("=" * 60)

            return True

        except Exception as e:
            self.logger.error(f"迁移异常: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

            # 发送迁移失败通知
            self.notifier.notify_migration_failed(
                source_ip=current_ip,
                target_ip=target_ip if target_ip else None,
                error_message=str(e),
                stage="执行异常"
            )

            # 释放锁
            if self.github.is_available():
                self.github.release_lock(target_ip, 'idle')
            return False
        finally:
            # 移除文件日志处理器
            self.logger.removeHandler(file_handler)
            file_handler.close()
    
    def cmd_feedback(self, source_ip: str):
        """
        新服务器启动后反馈状态
        
        Args:
            source_ip: 源服务器IP或域名
        """
        self.logger.info("=" * 60)
        self.logger.info("发送迁移反馈")
        self.logger.info("=" * 60)
        
        # 检查迁移标记
        flag_file = os.path.join(
            self.config['base']['install_path'],
            'data',
            'migration_flag.json'
        )
        
        if not os.path.exists(flag_file):
            self.logger.warning("未找到迁移标记文件")
            return False
        
        # 读取标记
        import json
        with open(flag_file, 'r') as f:
            flag_data = json.load(f)
        
        self.logger.info(f"迁移时间: {flag_data.get('migration_time')}")
        self.logger.info(f"源服务器: {flag_data.get('source_ip')}")
        
        # 向源服务器发送反馈
        self.logger.info(f"向源服务器发送反馈: {source_ip}")
        
        # 使用SSH发送简单的成功信号
        feedback_cmd = f"echo 'Migration successful from {get_current_ip()}' > /tmp/hermit_crab_feedback.txt"
        
        returncode, stdout, stderr = self.migrator.execute_remote_command(
            source_ip,
            feedback_cmd
        )
        
        if returncode == 0:
            self.logger.info("✅ 反馈发送成功")
            
            # 删除迁移标记
            os.remove(flag_file)
            
            # 更新自己的状态到GitHub
            if self.github.is_available():
                current_ip = get_current_ip()
                self.github.update_server_status(current_ip, 'active')
            
            return True
        else:
            self.logger.error(f"❌ 反馈发送失败: {stderr}")
            return False
    
    def cmd_daemon(self):
        """
        守护进程模式，持续监控
        """
        self.logger.info("=" * 60)
        self.logger.info("Hermit Crab 守护进程启动")
        self.logger.info("=" * 60)

        check_interval = self.config['lifecycle']['check_interval']

        while True:
            try:
                self.logger.info(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 执行检查...")

                # 首先从GitHub同步最新的服务器状态
                if self.github.is_available():
                    self.logger.debug("从GitHub同步最新服务器列表...")
                    nodes_data = self.github.pull_nodes()
                    if nodes_data:
                        self.scanner.save_nodes(nodes_data)
                        self.logger.debug("✅ 服务器列表已更新")

                # 检查是否需要迁移
                if self.cmd_check():
                    self.logger.warning("检测到需要迁移，开始自动迁移...")

                    # 自动迁移
                    success = self.cmd_migrate(auto=True)

                    if success:
                        self.logger.info("=" * 60)
                        self.logger.info("自动迁移成功！源服务器开始退役流程...")
                        self.logger.info("=" * 60)

                        # 迁移成功后，源服务器应该停止服务并退役
                        # 避免 systemd 自动重启后再次触发迁移
                        try:
                            import subprocess

                            self.logger.info("正在停止 hermit-crab-daemon 服务...")
                            subprocess.run(["systemctl", "stop", "hermit-crab-daemon.service"],
                                         check=False, capture_output=True)

                            self.logger.info("正在禁用 hermit-crab-daemon 服务...")
                            subprocess.run(["systemctl", "disable", "hermit-crab-daemon.service"],
                                         check=False, capture_output=True)

                            # 禁用邮件通知，避免退役服务器继续发送邮件
                            self.logger.info("禁用邮件通知...")
                            self.notifier._enabled = False

                            self.logger.info("✅ 源服务器已退役，不再执行监控任务和邮件通知")
                            self.logger.info("新服务器将接管所有服务")

                        except Exception as e:
                            self.logger.error(f"停止服务时出错: {e}")

                        # 退出守护进程
                        break
                    else:
                        self.logger.error("自动迁移失败，将在下次检查时重试")

                self.logger.info(f"下次检查时间: {check_interval}秒后")
                time.sleep(check_interval)

            except KeyboardInterrupt:
                self.logger.info("\n收到退出信号，守护进程停止")
                break
            except Exception as e:
                self.logger.error(f"守护进程异常: {e}")
                time.sleep(60)  # 发生异常后等待1分钟再继续
    
    def cmd_list(self):
        """列出所有服务器"""
        # 同步GitHub
        if self.github.is_available():
            nodes_data = self.github.pull_nodes()
            if nodes_data:
                self.scanner.save_nodes(nodes_data)

        self.scanner.list_servers()

    def cmd_start(self):
        """启动自动迁移"""
        import subprocess

        self.logger.info("=" * 60)
        self.logger.info("启动自动迁移")
        self.logger.info("=" * 60)

        try:
            # 检查当前状态
            result = subprocess.run(
                ["systemctl", "is-active", "hermit-crab-daemon.service"],
                capture_output=True, text=True, check=False
            )
            is_active = result.stdout.strip() == "active"

            if is_active:
                self.logger.info("✅ 自动迁移已在运行中")
                return

            # 启动服务
            self.logger.info("正在启动 hermit-crab-daemon 服务...")
            subprocess.run(
                ["systemctl", "enable", "--now", "hermit-crab-daemon.service"],
                check=True, capture_output=True
            )

            self.logger.info("✅ 自动迁移已启动")
            self.logger.info("系统将持续监控服务器状态并在需要时自动执行迁移")
            self.logger.info("=" * 60)

        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ 启动失败: {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"❌ 启动异常: {e}")
            sys.exit(1)

    def cmd_stop(self):
        """停止自动迁移"""
        import subprocess

        self.logger.info("=" * 60)
        self.logger.info("停止自动迁移")
        self.logger.info("=" * 60)

        try:
            # 检查当前状态
            result = subprocess.run(
                ["systemctl", "is-active", "hermit-crab-daemon.service"],
                capture_output=True, text=True, check=False
            )
            is_active = result.stdout.strip() == "active"

            if not is_active:
                self.logger.info("✅ 自动迁移未在运行")
                return

            # 停止服务
            self.logger.info("正在停止 hermit-crab-daemon 服务...")
            subprocess.run(
                ["systemctl", "disable", "--now", "hermit-crab-daemon.service"],
                check=True, capture_output=True
            )

            self.logger.info("✅ 自动迁移已停止")
            self.logger.info("需要手动执行 'hermit-crab migrate' 进行迁移")
            self.logger.info("=" * 60)

        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ 停止失败: {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"❌ 停止异常: {e}")
            sys.exit(1)

    def cmd_add_server(self, ip: str, notes: str = ""):
        """
        添加新服务器

        Args:
            ip: IP地址
            notes: 备注（可选）

        系统会自动记录当前时间作为添加日期
        """
        self.logger.info(f"添加新服务器: {ip}")

        # 添加到本地（系统自动记录时间）
        if self.scanner.add_server(ip, notes=notes):
            self.logger.info("✅ 已添加到本地列表")

            # 同步到GitHub
            if self.github.is_available():
                nodes_data = self.scanner.load_nodes()
                if self.github.push_nodes(nodes_data):
                    self.logger.info("✅ 已同步到GitHub")
                else:
                    self.logger.warning("⚠️  GitHub同步失败")

            # 计算过期日期
            from datetime import datetime, timedelta
            added_date = datetime.now()
            total_days = self.config['lifecycle']['total_days']
            expire_date = (added_date + timedelta(days=total_days)).strftime('%Y-%m-%d')

            # 发送服务器添加通知
            self.notifier.notify_server_added(
                server_ip=ip,
                added_by="管理员",
                notes=notes,
                expire_date=expire_date
            )

            return True
        else:
            self.logger.error("❌ 添加失败")
            return False

    def cmd_remove_server(self, ip: str):
        """
        删除服务器

        Args:
            ip: 服务器IP地址
        """
        self.logger.info(f"删除服务器: {ip}")

        # 从本地删除
        if self.scanner.remove_server(ip):
            self.logger.info("✅ 已从本地列表删除")

            # 同步到GitHub
            if self.github.is_available():
                nodes_data = self.scanner.load_nodes()
                if self.github.push_nodes(nodes_data):
                    self.logger.info("✅ 已同步到GitHub")
                else:
                    self.logger.warning("⚠️  GitHub同步失败")

            return True
        else:
            self.logger.error("❌ 删除失败")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Hermit Crab - 寄居蟹自动迁移系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 初始化生命周期（系统自动记录时间）
  %(prog)s init
  
  # 查看状态
  %(prog)s status
  
  # 检查是否需要迁移
  %(prog)s check
  
  # 手动迁移到指定服务器
  %(prog)s migrate --target 192.168.1.11 --password your_password

  # 自动选择并迁移
  %(prog)s migrate --auto --password your_password

  # 强制迁移到剩余时间最长的服务器（忽略生命周期检查）
  %(prog)s migrate --auto --force
  
  # 守护进程模式
  %(prog)s daemon
  
  # 列出所有服务器
  %(prog)s list

  # 添加新服务器（系统自动记录时间）
  %(prog)s add --ip 192.168.1.12
  %(prog)s add --ip 192.168.1.13 --notes "备份服务器"

  # 删除服务器
  %(prog)s remove --ip 192.168.1.10
        """
    )
    
    # 配置从 .env 文件读取，无需命令行参数
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # init命令
    init_parser = subparsers.add_parser('init', help='初始化生命周期（系统自动记录时间）')

    # update-lifecycle命令（迁移后使用）
    update_lifecycle_parser = subparsers.add_parser('update-lifecycle', help='迁移后更新生命周期（保留历史）')
    update_lifecycle_parser.add_argument('--target-ip', help='目标服务器IP（可选）')
    update_lifecycle_parser.add_argument('--old-lifecycle', help='源服务器的lifecycle JSON（可选）')
    update_lifecycle_parser.add_argument('--old-lifecycle-base64', help='源服务器的lifecycle base64编码（可选）')

    # status命令
    subparsers.add_parser('status', help='显示当前状态')
    
    # check命令
    subparsers.add_parser('check', help='检查是否需要迁移')
    
    # migrate命令
    migrate_parser = subparsers.add_parser('migrate', help='执行迁移')
    migrate_parser.add_argument('--target', help='目标服务器IP或域名')
    migrate_parser.add_argument('--password', help='SSH密码（可选，优先从环境变量读取）')
    migrate_parser.add_argument('--auto', action='store_true', help='自动选择目标')
    migrate_parser.add_argument('--force', action='store_true', help='强制迁移（忽略生命周期，选择剩余时间最长的服务器）')
    
    # feedback命令
    feedback_parser = subparsers.add_parser('feedback', help='发送迁移反馈')
    feedback_parser.add_argument('--source', required=True, help='源服务器IP或域名')
    
    # daemon命令
    subparsers.add_parser('daemon', help='守护进程模式')

    # start命令
    subparsers.add_parser('start', help='启动自动迁移')

    # stop命令
    subparsers.add_parser('stop', help='停止自动迁移')

    # list命令
    subparsers.add_parser('list', help='列出所有服务器')

    # add命令
    add_parser = subparsers.add_parser('add', help='添加新服务器（系统自动记录时间）')
    add_parser.add_argument('--ip', required=True, help='服务器IP地址')
    add_parser.add_argument('--notes', default='', help='备注信息（可选）')

    # remove命令
    remove_parser = subparsers.add_parser('remove', help='删除服务器')
    remove_parser.add_argument('--ip', required=True, help='服务器IP地址')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 创建Agent实例
    agent = HermitCrabAgent()
    
    # 执行命令
    try:
        if args.command == 'init':
            agent.cmd_init()
        elif args.command == 'update-lifecycle':
            agent.cmd_update_lifecycle(args.target_ip, args.old_lifecycle, args.old_lifecycle_base64)
        elif args.command == 'status':
            agent.cmd_status()
        elif args.command == 'check':
            agent.cmd_check()
        elif args.command == 'migrate':
            agent.cmd_migrate(args.target, args.password, args.auto, args.force)
        elif args.command == 'feedback':
            agent.cmd_feedback(args.source)
        elif args.command == 'daemon':
            agent.cmd_daemon()
        elif args.command == 'start':
            agent.cmd_start()
        elif args.command == 'stop':
            agent.cmd_stop()
        elif args.command == 'list':
            agent.cmd_list()
        elif args.command == 'add':
            agent.cmd_add_server(args.ip, args.notes)
        elif args.command == 'remove':
            agent.cmd_remove_server(args.ip)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        agent.logger.error(f"执行命令失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

