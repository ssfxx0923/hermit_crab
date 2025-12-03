"""
迁移模块
负责执行整机克隆和数据传输
"""

import os
import time
import subprocess
import shlex
from typing import Dict, List, Optional
from .utils import Logger, run_command, check_command_exists, install_package


class Migrator:
    """服务器迁移执行器"""
    
    def __init__(self, config: Dict):
        """
        初始化迁移器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = Logger().get_logger()
        self.ssh_user = config['security']['ssh_user']
        self.ssh_key = config['security']['ssh_key_path']
        
        # 检查必要工具
        self._check_dependencies()
    
    def _check_dependencies(self):
        """检查并安装必要的依赖"""
        required_tools = ['rsync', 'ssh', 'sshpass', 'tar']
        
        for tool in required_tools:
            if not check_command_exists(tool):
                self.logger.warning(f"{tool} 未安装，尝试安装...")
                if not install_package(tool):
                    raise RuntimeError(f"无法安装必要工具: {tool}")
    
    def test_ssh_connection(self, target_ip: str, password: Optional[str] = None) -> bool:
        """
        测试SSH连接
        
        Args:
            target_ip: 目标服务器IP
            password: SSH密码（如果使用密码认证）
            
        Returns:
            连接是否成功
        """
        self.logger.info(f"测试SSH连接: {target_ip}")

        # 清除旧的SSH主机密钥记录（防止重装服务器后密钥变化导致连接失败）
        self.logger.debug(f"清除 {target_ip} 的SSH主机密钥记录...")
        run_command(f"ssh-keygen -R {target_ip} 2>/dev/null", timeout=10)

        if password:
            escaped_password = shlex.quote(password)
            cmd = f"sshpass -p {escaped_password} ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {self.ssh_user}@{target_ip} 'echo SUCCESS'"
        else:
            cmd = f"ssh -i {self.ssh_key} -o StrictHostKeyChecking=no -o ConnectTimeout=10 {self.ssh_user}@{target_ip} 'echo SUCCESS'"
        
        returncode, stdout, stderr = run_command(cmd, timeout=30)
        
        if returncode == 0 and 'SUCCESS' in stdout:
            self.logger.info("SSH连接测试成功")
            return True
        else:
            self.logger.error(f"SSH连接失败: {stderr}")
            return False
    
    def setup_ssh_key(self, target_ip: str, password: str) -> bool:
        """
        设置SSH密钥免密登录
        
        Args:
            target_ip: 目标服务器IP
            password: SSH密码
            
        Returns:
            是否成功
        """
        self.logger.info(f"配置SSH密钥到 {target_ip}")
        
        # 确保本地密钥存在
        if not os.path.exists(self.ssh_key):
            self.logger.info("生成SSH密钥对...")
            os.makedirs(os.path.dirname(self.ssh_key), exist_ok=True)
            cmd = f"ssh-keygen -t rsa -b 4096 -f {self.ssh_key} -N ''"
            returncode, _, stderr = run_command(cmd)
            
            if returncode != 0:
                self.logger.error(f"生成SSH密钥失败: {stderr}")
                return False
        
        # 复制公钥到目标服务器
        pub_key = f"{self.ssh_key}.pub"
        if not os.path.exists(pub_key):
            self.logger.error(f"公钥文件不存在: {pub_key}")
            return False

        escaped_password = shlex.quote(password)
        cmd = f"sshpass -p {escaped_password} ssh-copy-id -i {pub_key} -o StrictHostKeyChecking=no {self.ssh_user}@{target_ip}"
        returncode, stdout, stderr = run_command(cmd, timeout=60)
        
        if returncode == 0:
            self.logger.info("SSH密钥配置成功")
            return True
        else:
            self.logger.error(f"SSH密钥配置失败: {stderr}")
            return False
    
    def execute_remote_command(self, target_ip: str, command: str, 
                               use_password: bool = False, 
                               password: Optional[str] = None) -> tuple:
        """
        在远程服务器执行命令
        
        Args:
            target_ip: 目标服务器IP
            command: 要执行的命令
            use_password: 是否使用密码
            password: SSH密码
            
        Returns:
            (returncode, stdout, stderr)
        """
        if use_password and password:
            escaped_password = shlex.quote(password)
            cmd = f"sshpass -p {escaped_password} ssh -o StrictHostKeyChecking=no {self.ssh_user}@{target_ip} '{command}'"
        else:
            cmd = f"ssh -i {self.ssh_key} -o StrictHostKeyChecking=no {self.ssh_user}@{target_ip} '{command}'"
        
        return run_command(cmd, timeout=300)
    
    def rsync_system_files(self, target_ip: str) -> bool:
        """
        使用Rsync同步系统文件
        
        Args:
            target_ip: 目标服务器IP
            
        Returns:
            是否成功
        """
        self.logger.info("=" * 60)
        self.logger.info("开始Rsync系统文件同步...")
        self.logger.info("=" * 60)
        
        exclude_file = self.config['rsync']['exclude_file']
        extra_args = self.config['rsync']['extra_args']
        bandwidth_limit = self.config['rsync']['bandwidth_limit']
        
        # 构建rsync命令
        cmd_parts = [
            'rsync',
            extra_args,
            f'--exclude-from={exclude_file}'
        ]
        
        # 添加带宽限制
        if bandwidth_limit > 0:
            cmd_parts.append(f'--bwlimit={bandwidth_limit}')
        
        # 使用SSH密钥
        cmd_parts.append(f'-e "ssh -i {self.ssh_key} -o StrictHostKeyChecking=no"')
        
        # 源和目标
        cmd_parts.append('/')
        cmd_parts.append(f'{self.ssh_user}@{target_ip}:/')
        
        cmd = ' '.join(cmd_parts)
        
        self.logger.info(f"执行命令: {cmd}")
        
        # 执行rsync
        start_time = time.time()

        try:
            # 输出到终端显示进度，不完全记录到日志
            self.logger.info("Rsync 传输中，实时进度显示：")
            self.logger.info("-" * 60)

            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # 实时输出到终端
            line_count = 0
            for line in process.stdout:
                line = line.strip()
                if line:
                    # 直接打印到终端（不经过logger，避免日志文件过大）
                    print(line, flush=True)
                    line_count += 1

                    # 每100行记录一次统计到日志
                    if line_count % 100 == 0:
                        self.logger.debug(f"已处理 {line_count} 个文件...")

            process.wait()

            elapsed = time.time() - start_time
            self.logger.info("-" * 60)
            self.logger.info(f"传输统计: 共处理 {line_count} 个文件/目录")

            if process.returncode == 0:
                self.logger.info(f"✅ Rsync同步完成 (耗时: {elapsed:.2f}秒)")
                return True
            else:
                self.logger.error(f"❌ Rsync同步失败 (返回码: {process.returncode})")
                return False

        except Exception as e:
            self.logger.error(f"Rsync执行异常: {e}")
            return False
    
    def tar_stream_transfer(self, target_ip: str, directories: List[str]) -> bool:
        """
        使用Tar Stream传输大目录
        
        Args:
            target_ip: 目标服务器IP
            directories: 要传输的目录列表
            
        Returns:
            是否成功
        """
        self.logger.info("=" * 60)
        self.logger.info("开始Tar Stream传输...")
        self.logger.info("=" * 60)
        
        for directory in directories:
            if not os.path.exists(directory):
                self.logger.warning(f"目录不存在，跳过: {directory}")
                continue
            
            self.logger.info(f"传输目录: {directory}")
            
            # 构建tar stream命令
            cmd = (
                f"tar -czf - {directory} | "
                f"ssh -i {self.ssh_key} -o StrictHostKeyChecking=no "
                f"{self.ssh_user}@{target_ip} 'cd / && tar -xzf -'"
            )
            
            start_time = time.time()
            returncode, stdout, stderr = run_command(cmd, timeout=7200)
            elapsed = time.time() - start_time
            
            if returncode == 0:
                self.logger.info(f"✅ {directory} 传输完成 (耗时: {elapsed:.2f}秒)")
            else:
                self.logger.error(f"❌ {directory} 传输失败: {stderr}")
                return False
        
        self.logger.info("Tar Stream传输全部完成")
        return True
    
    def backup_critical_files(self, target_ip: str) -> bool:
        """
        在目标服务器备份关键文件
        
        Args:
            target_ip: 目标服务器IP
            
        Returns:
            是否成功
        """
        self.logger.info("在目标服务器备份关键文件...")
        
        backup_commands = [
            "mkdir -p /root/backup_before_migration",
            "cp -a /etc/fstab /root/backup_before_migration/ 2>/dev/null || true",
            "cp -a /etc/netplan /root/backup_before_migration/ 2>/dev/null || true",
            "cp -a /etc/hostname /root/backup_before_migration/ 2>/dev/null || true",
            "cp -a /etc/hosts /root/backup_before_migration/ 2>/dev/null || true",
        ]
        
        for cmd in backup_commands:
            returncode, _, stderr = self.execute_remote_command(target_ip, cmd)
            if returncode != 0:
                self.logger.warning(f"备份命令执行警告: {stderr}")
        
        self.logger.info("关键文件备份完成")
        return True
    
    def restore_network_config(self, target_ip: str, password: Optional[str] = None) -> bool:
        """
        恢复目标服务器的网络配置

        Args:
            target_ip: 目标服务器IP
            password: SSH密码（可选，SSH密钥不可用时使用）

        Returns:
            是否成功
        """
        self.logger.info("恢复目标服务器网络配置...")

        restore_commands = [
            "cp -a /root/backup_before_migration/netplan/* /etc/netplan/ 2>/dev/null || true",
            "cp -a /root/backup_before_migration/hostname /etc/hostname 2>/dev/null || true",
            "cp -a /root/backup_before_migration/hosts /etc/hosts 2>/dev/null || true",
            "netplan apply 2>/dev/null || true"
        ]

        for cmd in restore_commands:
            # 尝试使用SSH密钥
            returncode, _, stderr = self.execute_remote_command(target_ip, cmd)

            # 如果失败且有密码，尝试使用密码
            if returncode != 0 and password:
                self.logger.debug(f"SSH密钥执行失败，尝试使用密码: {cmd}")
                returncode, _, stderr = self.execute_remote_command(target_ip, cmd, use_password=True, password=password)

            if returncode != 0:
                self.logger.warning(f"恢复命令执行警告: {stderr}")

        self.logger.info("网络配置恢复完成")
        return True
    
    def perform_migration(self, target_ip: str, password: Optional[str] = None) -> bool:
        """
        执行完整迁移流程
        
        Args:
            target_ip: 目标服务器IP
            password: SSH密码（首次连接需要）
            
        Returns:
            是否成功
        """
        self.logger.info("=" * 60)
        self.logger.info(f"开始迁移到目标服务器: {target_ip}")
        self.logger.info("=" * 60)
        
        try:
            # 1. 测试SSH连接
            if password:
                if not self.test_ssh_connection(target_ip, password):
                    self.logger.error("SSH连接测试失败")
                    return False
                
                # 2. 设置SSH密钥
                if not self.setup_ssh_key(target_ip, password):
                    self.logger.error("SSH密钥设置失败")
                    return False
            else:
                if not self.test_ssh_connection(target_ip):
                    self.logger.error("SSH连接测试失败（使用密钥）")
                    return False
            
            # 3. 备份目标服务器关键文件
            if not self.backup_critical_files(target_ip):
                self.logger.error("备份关键文件失败")
                return False
            
            # 4. 执行Rsync系统同步
            if not self.rsync_system_files(target_ip):
                self.logger.error("Rsync系统同步失败")
                return False

            # 5. 重新配置SSH密钥（rsync会覆盖authorized_keys）
            if password:
                self.logger.info("重新配置SSH密钥（rsync后）...")
                if not self.setup_ssh_key(target_ip, password):
                    self.logger.error("重新配置SSH密钥失败")
                    return False

            # 6. 恢复网络配置（传递密码作为备用）
            if not self.restore_network_config(target_ip, password):
                self.logger.error("恢复网络配置失败")
                return False

            # 7. Tar Stream传输大目录
            tar_dirs = self.config['migration'].get('tar_stream_dirs', [])
            if tar_dirs:
                if not self.tar_stream_transfer(target_ip, tar_dirs):
                    self.logger.warning("Tar Stream传输部分失败，但继续...")
            
            self.logger.info("=" * 60)
            self.logger.info("✅ 迁移完成！")
            self.logger.info("=" * 60)

            return True

        except Exception as e:
            self.logger.error(f"迁移过程中发生异常: {e}")
            return False

    def sync_final_updates(self, target_ip: str, password: Optional[str] = None) -> bool:
        """
        迁移完成后，同步最新的日志和数据到新服务器

        这个方法在所有迁移操作完成后调用，确保新服务器获得：
        1. 完整的迁移日志
        2. 更新后的 lifecycle.json（包含完整迁移历史）
        3. 更新后的 nodes.json

        Args:
            target_ip: 目标服务器IP
            password: SSH密码

        Returns:
            是否成功
        """
        self.logger.info("开始同步最新日志和数据...")

        install_path = self.config['base']['install_path']

        # 只同步关键的数据和日志目录，避免全盘扫描
        sync_paths = [
            f"{install_path}/data/",           # lifecycle.json, nodes.json 等
            f"{install_path}/logs/",           # 所有日志文件
            f"{install_path}/.env",            # 配置文件
        ]

        success = True
        for path in sync_paths:
            # 检查路径是否存在
            if not os.path.exists(path):
                self.logger.debug(f"跳过不存在的路径: {path}")
                continue

            # 构建 rsync 命令
            if os.path.isdir(path):
                # 目录需要加 /
                src = path if path.endswith('/') else path + '/'
                dest = f"{self.ssh_user}@{target_ip}:{path}"
            else:
                # 文件
                src = path
                dest = f"{self.ssh_user}@{target_ip}:{path}"

            rsync_cmd = [
                'rsync',
                '-aAXvz',               # 基本选项
                '--numeric-ids',        # 保留用户ID
                '--delete',             # 删除目标中多余的文件
                '-e', f'ssh -i {self.ssh_key} -o StrictHostKeyChecking=no',
                src,
                dest
            ]

            self.logger.info(f"同步: {path}")

            try:
                result = subprocess.run(
                    rsync_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )

                if result.returncode == 0:
                    self.logger.debug(f"✅ {path} 同步成功")
                else:
                    self.logger.warning(f"⚠️  {path} 同步失败: {result.stderr}")
                    success = False

            except subprocess.TimeoutExpired:
                self.logger.error(f"❌ {path} 同步超时")
                success = False
            except Exception as e:
                self.logger.error(f"❌ {path} 同步异常: {e}")
                success = False

        if success:
            self.logger.info("✅ 所有最新数据已同步")
        else:
            self.logger.warning("⚠️  部分数据同步失败")

        return success

