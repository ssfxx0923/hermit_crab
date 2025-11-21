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
    Logger, load_config, get_current_ip, format_date,
    Monitor, Scanner, Migrator, Initializer,
    GitHubSync, CloudFlareAPI
)


class HermitCrabAgent:
    """Hermit Crab主控制器"""
    
    def __init__(self, config_path: str = "/opt/hermit_crab/config.yaml"):
        """
        初始化Agent
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = load_config(config_path)
        
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
        
        self.logger.info("Hermit Crab Agent 已启动")
    
    def cmd_init(self, added_date: str = None, domain: str = None):
        """
        初始化生命周期
        
        Args:
            added_date: 添加日期
            domain: 当前域名
        """
        self.logger.info("=" * 60)
        self.logger.info("初始化 Hermit Crab")
        self.logger.info("=" * 60)
        
        # 初始化生命周期
        lifecycle = self.monitor.initialize_lifecycle(added_date)
        
        # 更新配置中的域名
        if domain:
            self.config['base']['current_domain'] = domain
            self.logger.info(f"当前域名: {domain}")
        
        self.logger.info("✅ 初始化完成")
        self.monitor.display_status()
    
    def cmd_status(self):
        """显示当前状态"""
        self.monitor.display_status()
        
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
        return True
    
    def cmd_migrate(self, target_ip: str = None, password: str = None, auto: bool = False):
        """
        执行迁移
        
        Args:
            target_ip: 目标服务器IP（可选，自动选择）
            password: SSH密码
            auto: 是否自动模式（自动选择目标）
        """
        self.logger.info("=" * 60)
        self.logger.info("开始执行迁移流程")
        self.logger.info("=" * 60)
        
        # 1. 检查是否需要迁移
        status = self.monitor.get_status()
        
        if not status['initialized']:
            self.logger.error("❌ 生命周期未初始化")
            return False
        
        current_remaining = status['remaining_days']
        self.logger.info(f"当前服务器剩余: {current_remaining} 天")
        
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
            target_server = self.scanner.select_target_server(current_remaining)
            
            if target_server is None:
                self.logger.error("❌ 没有合适的目标服务器")
                return False
            
            target_ip = target_server['ip']
            target_domain = target_server['domain']
            target_id = target_server['id']
        else:
            # 手动指定IP，查找对应服务器信息
            available = self.scanner.get_available_servers()
            target_server = None
            
            for server in available:
                if server['ip'] == target_ip or server.get('domain') == target_ip:
                    target_server = server
                    target_ip = server['ip']
                    target_domain = server['domain']
                    target_id = server['id']
                    break
            
            if target_server is None:
                self.logger.error(f"❌ 目标服务器不在可用列表中: {target_ip}")
                return False
        
        self.logger.info(f"目标服务器: {target_domain} ({target_ip})")
        self.logger.info(f"目标剩余时间: {target_server['remaining_days']} 天")
        
        # 4. 获取锁（防止并发）
        if self.github.is_available():
            current_domain = self.config['base']['current_domain']
            self.logger.info(f"尝试获取服务器锁: {target_id}")
            
            if not self.github.acquire_lock(target_id, current_domain):
                self.logger.error("❌ 无法获取服务器锁，可能已被其他服务器选中")
                return False
        else:
            # 本地更新状态
            self.scanner.update_server_status(target_id, 'transferring')
        
        try:
            # 5. 执行迁移
            if not self.migrator.perform_migration(target_ip, password):
                self.logger.error("❌ 迁移失败")
                # 释放锁
                if self.github.is_available():
                    self.github.release_lock(target_id, 'idle')
                return False
            
            # 6. 初始化目标服务器
            if not self.initializer.initialize_target_server(target_ip, target_server, self.migrator):
                self.logger.error("❌ 目标服务器初始化失败")
                # 释放锁
                if self.github.is_available():
                    self.github.release_lock(target_id, 'idle')
                return False
            
            # 7. 更新DNS（如果启用）
            if self.cloudflare.is_available():
                current_subdomain = self.config['base']['current_domain'].split('.')[0]
                self.logger.info(f"更新DNS: {current_subdomain} -> {target_ip}")
                
                if self.cloudflare.update_domain_for_migration(current_subdomain, target_ip):
                    self.logger.info("✅ DNS已更新")
                else:
                    self.logger.warning("⚠️  DNS更新失败，可能需要手动更新")
            
            # 8. 更新服务器状态
            if self.github.is_available():
                self.github.update_server_status(target_id, 'active')
            else:
                self.scanner.update_server_status(target_id, 'active')
            
            # 9. 记录迁移历史
            self.monitor.add_migration_record(target_server)
            
            self.logger.info("=" * 60)
            self.logger.info("🎉 迁移流程全部完成！")
            self.logger.info("=" * 60)
            self.logger.info(f"新服务器: {target_domain} ({target_ip})")
            self.logger.info("请等待新服务器的反馈...")
            
            return True
            
        except Exception as e:
            self.logger.error(f"迁移异常: {e}")
            # 释放锁
            if self.github.is_available():
                self.github.release_lock(target_id, 'idle')
            return False
    
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
                current_domain = self.config['base']['current_domain']
                self.github.update_server_status(current_domain, 'active')
            
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
                
                # 检查是否需要迁移
                if self.cmd_check():
                    self.logger.warning("检测到需要迁移，开始自动迁移...")
                    
                    # 自动迁移
                    success = self.cmd_migrate(auto=True)
                    
                    if success:
                        self.logger.info("自动迁移成功！")
                        # 迁移成功后退出守护进程（因为已经转移到新服务器）
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
    
    def cmd_add_server(self, ip: str, domain: str, added_date: str, 
                      expire_date: str, notes: str = ""):
        """
        添加新服务器
        
        Args:
            ip: IP地址
            domain: 域名
            added_date: 添加日期
            expire_date: 过期日期
            notes: 备注
        """
        self.logger.info(f"添加新服务器: {domain} ({ip})")
        
        # 添加到本地
        if self.scanner.add_server(ip, domain, added_date, expire_date, notes=notes):
            self.logger.info("✅ 已添加到本地列表")
            
            # 同步到GitHub
            if self.github.is_available():
                nodes_data = self.scanner.load_nodes()
                if self.github.push_nodes(nodes_data):
                    self.logger.info("✅ 已同步到GitHub")
                else:
                    self.logger.warning("⚠️  GitHub同步失败")
            
            return True
        else:
            self.logger.error("❌ 添加失败")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Hermit Crab - 寄居蟹自动迁移系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 初始化生命周期
  %(prog)s init --added-date 2025-11-21 --domain a.ssfxx.com
  
  # 查看状态
  %(prog)s status
  
  # 检查是否需要迁移
  %(prog)s check
  
  # 手动迁移到指定服务器
  %(prog)s migrate --target 192.168.1.11 --password your_password
  
  # 自动选择并迁移
  %(prog)s migrate --auto --password your_password
  
  # 守护进程模式
  %(prog)s daemon
  
  # 列出所有服务器
  %(prog)s list
  
  # 添加新服务器
  %(prog)s add --ip 192.168.1.12 --domain server-3.ssfxx.com \\
               --added-date 2025-11-21 --expire-date 2025-12-06
        """
    )
    
    parser.add_argument('-c', '--config', default='/opt/hermit_crab/config.yaml',
                       help='配置文件路径')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # init命令
    init_parser = subparsers.add_parser('init', help='初始化生命周期')
    init_parser.add_argument('--added-date', help='添加日期 (YYYY-MM-DD)')
    init_parser.add_argument('--domain', help='当前域名')
    
    # status命令
    subparsers.add_parser('status', help='显示当前状态')
    
    # check命令
    subparsers.add_parser('check', help='检查是否需要迁移')
    
    # migrate命令
    migrate_parser = subparsers.add_parser('migrate', help='执行迁移')
    migrate_parser.add_argument('--target', help='目标服务器IP或域名')
    migrate_parser.add_argument('--password', help='SSH密码')
    migrate_parser.add_argument('--auto', action='store_true', help='自动选择目标')
    
    # feedback命令
    feedback_parser = subparsers.add_parser('feedback', help='发送迁移反馈')
    feedback_parser.add_argument('--source', required=True, help='源服务器IP或域名')
    
    # daemon命令
    subparsers.add_parser('daemon', help='守护进程模式')
    
    # list命令
    subparsers.add_parser('list', help='列出所有服务器')
    
    # add命令
    add_parser = subparsers.add_parser('add', help='添加新服务器')
    add_parser.add_argument('--ip', required=True, help='IP地址')
    add_parser.add_argument('--domain', required=True, help='域名')
    add_parser.add_argument('--added-date', required=True, help='添加日期 (YYYY-MM-DD)')
    add_parser.add_argument('--expire-date', required=True, help='过期日期 (YYYY-MM-DD)')
    add_parser.add_argument('--notes', default='', help='备注')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 创建Agent实例
    agent = HermitCrabAgent(args.config)
    
    # 执行命令
    try:
        if args.command == 'init':
            agent.cmd_init(args.added_date, args.domain)
        elif args.command == 'status':
            agent.cmd_status()
        elif args.command == 'check':
            agent.cmd_check()
        elif args.command == 'migrate':
            agent.cmd_migrate(args.target, args.password, args.auto)
        elif args.command == 'feedback':
            agent.cmd_feedback(args.source)
        elif args.command == 'daemon':
            agent.cmd_daemon()
        elif args.command == 'list':
            agent.cmd_list()
        elif args.command == 'add':
            agent.cmd_add_server(
                args.ip, args.domain, args.added_date,
                args.expire_date, args.notes
            )
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        agent.logger.error(f"执行命令失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

