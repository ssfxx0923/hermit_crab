"""
初始化模块
负责在新服务器上配置环境和启动服务
"""

import os
import time
from typing import Dict
from .utils import Logger, format_datetime


class Initializer:
    """新服务器初始化器"""
    
    def __init__(self, config: Dict):
        """
        初始化器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = Logger().get_logger()
        self.install_path = config['base']['install_path']
    
    def sync_config_to_target(self, target_ip: str, migrator) -> bool:
        """
        同步配置文件到目标服务器

        Args:
            target_ip: 目标服务器IP
            migrator: Migrator实例（用于执行远程命令）

        Returns:
            是否成功
        """
        self.logger.info("同步配置文件到目标服务器...")

        # 配置文件列表（.env 和 nodes.json 已通过 rsync 复制，这里只确认）
        config_files = [
            f"{self.install_path}/.env",
            f"{self.install_path}/data/nodes.json"
        ]

        for config_file in config_files:
            if not os.path.exists(config_file):
                self.logger.warning(f"配置文件不存在: {config_file}")
                continue

            # 使用scp传输（确保最新版本）
            cmd = (
                f"scp -i {migrator.ssh_key} -o StrictHostKeyChecking=no "
                f"{config_file} {migrator.ssh_user}@{target_ip}:{config_file}"
            )

            import subprocess
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                self.logger.info(f"✅ 已同步: {config_file}")
            else:
                self.logger.error(f"❌ 同步失败: {config_file}, 错误: {result.stderr}")
                return False

        return True
    
    def update_lifecycle_on_target(self, target_ip: str, migrator) -> bool:
        """
        更新目标服务器的生命周期信息

        Args:
            target_ip: 目标服务器IP
            migrator: Migrator实例

        Returns:
            是否成功
        """
        self.logger.info("更新目标服务器生命周期信息...")

        # 创建初始化命令（系统自动记录时间）
        cmd = f"cd {self.install_path} && python3 agent.py init"

        returncode, _, stderr = migrator.execute_remote_command(target_ip, cmd)

        if returncode == 0:
            self.logger.info("✅ 生命周期信息已更新")
            return True
        else:
            self.logger.error(f"❌ 更新生命周期失败: {stderr}")
            return False
    
    def setup_systemd_service_on_target(self, target_ip: str, migrator) -> bool:
        """
        在目标服务器上配置systemd服务
        
        Args:
            target_ip: 目标服务器IP
            migrator: Migrator实例
            
        Returns:
            是否成功
        """
        self.logger.info("配置目标服务器systemd服务...")
        
        commands = [
            # 创建systemd服务文件已经通过rsync复制过去了
            # 重新加载systemd
            "systemctl daemon-reload",
            # 启用服务
            "systemctl enable hermit-crab.service",
            # 启用定时器
            "systemctl enable hermit-crab.timer",
        ]
        
        for cmd in commands:
            returncode, _, stderr = migrator.execute_remote_command(target_ip, cmd)

            if returncode != 0:
                self.logger.warning(f"命令执行警告: {cmd}, 错误: {stderr}")
        
        self.logger.info("✅ Systemd服务配置完成")
        return True
    
    def create_migration_flag(self, target_ip: str, migrator) -> bool:
        """
        在目标服务器创建迁移标记文件
        
        Args:
            target_ip: 目标服务器IP
            migrator: Migrator实例
            
        Returns:
            是否成功
        """
        self.logger.info("创建迁移标记文件...")
        
        # 获取当前服务器IP
        from .utils import get_current_ip
        source_ip = get_current_ip()
        
        flag_content = f"""{{
    "migrated": true,
    "migration_time": "{format_datetime()}",
    "source_ip": "{source_ip}",
    "target_ip": "{target_ip}"
}}"""
        
        cmd = f"echo '{flag_content}' > {self.install_path}/data/migration_flag.json"
        
        returncode, _, stderr = migrator.execute_remote_command(target_ip, cmd)
        
        if returncode == 0:
            self.logger.info("✅ 迁移标记已创建")
            return True
        else:
            self.logger.error(f"❌ 创建迁移标记失败: {stderr}")
            return False
    
    def cleanup_python_cache(self, target_ip: str, migrator) -> bool:
        """
        清理 Python 字节码缓存（避免跨机器兼容性问题）

        Args:
            target_ip: 目标服务器IP
            migrator: Migrator实例

        Returns:
            是否成功
        """
        self.logger.info("清理 Python 字节码缓存...")

        cleanup_commands = [
            "find /usr -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true",
            "find /usr/local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true",
            "find /root -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true",
            "find /home -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true",
        ]

        for cmd in cleanup_commands:
            self.logger.debug(f"执行: {cmd}")
            migrator.execute_remote_command(target_ip, cmd)

        self.logger.info("✅ Python 缓存清理完成")
        return True

    def reboot_target_server(self, target_ip: str, migrator) -> bool:
        """
        重启目标服务器

        Args:
            target_ip: 目标服务器IP
            migrator: Migrator实例

        Returns:
            是否成功
        """
        self.logger.info("准备重启目标服务器...")

        # 检查调试模式
        if self.config.get('debug', {}).get('skip_reboot', False):
            self.logger.warning("⚠️  调试模式：跳过重启")
            return True

        # 发送重启命令
        cmd = "nohup sh -c 'sleep 2 && reboot' >/dev/null 2>&1 &"

        returncode, _, stderr = migrator.execute_remote_command(target_ip, cmd)

        if returncode == 0:
            self.logger.info("✅ 重启命令已发送")
            self.logger.info("⏳ 等待服务器重启...")
            time.sleep(10)
            return True
        else:
            self.logger.error(f"❌ 重启命令失败: {stderr}")
            return False
    
    def wait_for_target_online(self, target_ip: str, migrator, 
                               max_wait: int = 300, check_interval: int = 10) -> bool:
        """
        等待目标服务器上线
        
        Args:
            target_ip: 目标服务器IP
            migrator: Migrator实例
            max_wait: 最大等待时间（秒）
            check_interval: 检查间隔（秒）
            
        Returns:
            是否成功上线
        """
        self.logger.info(f"等待目标服务器上线 (最多等待 {max_wait} 秒)...")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if migrator.test_ssh_connection(target_ip):
                elapsed = time.time() - start_time
                self.logger.info(f"✅ 目标服务器已上线 (耗时: {elapsed:.0f}秒)")
                return True
            
            self.logger.debug(f"服务器未响应，{check_interval}秒后重试...")
            time.sleep(check_interval)
        
        self.logger.error(f"❌ 等待超时，服务器未能在 {max_wait} 秒内上线")
        return False
    
    def verify_services_on_target(self, target_ip: str, migrator) -> bool:
        """
        验证目标服务器上的服务状态
        
        Args:
            target_ip: 目标服务器IP
            migrator: Migrator实例
            
        Returns:
            是否成功
        """
        self.logger.info("验证目标服务器服务状态...")
        
        check_commands = [
            ("Hermit Crab服务", "systemctl is-active hermit-crab.service"),
            ("Hermit Crab定时器", "systemctl is-active hermit-crab.timer"),
        ]
        
        all_ok = True
        for name, cmd in check_commands:
            returncode, stdout, _ = migrator.execute_remote_command(target_ip, cmd)

            if returncode == 0 and 'active' in stdout:
                self.logger.info(f"✅ {name}: 运行中")
            else:
                self.logger.warning(f"⚠️  {name}: 未运行")
                all_ok = False
        
        return all_ok
    
    def initialize_target_server(self, target_ip: str, target_server: Dict, migrator) -> bool:
        """
        完整初始化目标服务器
        
        Args:
            target_ip: 目标服务器IP
            target_server: 目标服务器信息
            migrator: Migrator实例
            
        Returns:
            是否成功
        """
        self.logger.info("=" * 60)
        self.logger.info("开始初始化目标服务器")
        self.logger.info("=" * 60)
        
        try:
            # 1. 同步配置文件
            if not self.sync_config_to_target(target_ip, migrator):
                return False

            # 2. 清理 Python 字节码缓存（跨机器可能不兼容）
            if not self.cleanup_python_cache(target_ip, migrator):
                return False

            # 3. 更新生命周期
            if not self.update_lifecycle_on_target(target_ip, migrator):
                return False

            # 4. 配置systemd服务
            if not self.setup_systemd_service_on_target(target_ip, migrator):
                return False

            # 5. 创建迁移标记
            if not self.create_migration_flag(target_ip, migrator):
                return False

            # 6. 重启目标服务器
            if not self.reboot_target_server(target_ip, migrator):
                return False

            # 7. 等待服务器上线
            startup_wait = self.config['feedback']['startup_wait']
            if not self.wait_for_target_online(target_ip, migrator, max_wait=startup_wait):
                self.logger.warning("⚠️  服务器重启超时，可能需要手动检查")
                return False

            # 8. 验证服务状态
            self.verify_services_on_target(target_ip, migrator)
            
            self.logger.info("=" * 60)
            self.logger.info("✅ 目标服务器初始化完成")
            self.logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            self.logger.error(f"初始化过程中发生异常: {e}")
            return False

