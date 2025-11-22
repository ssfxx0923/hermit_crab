"""
工具函数模块
提供日志、配置加载、网络检测等通用功能
"""

import os
import sys
import logging
import socket
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional
import colorlog
from dotenv import load_dotenv


class Logger:
    """日志管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = None
    
    def setup(self, log_level: str = "INFO", log_file: Optional[str] = None):
        """设置日志"""
        # 创建logger
        self.logger = logging.getLogger("HermitCrab")
        self.logger.setLevel(getattr(logging, log_level))
        
        # 清除已有的handlers
        self.logger.handlers.clear()
        
        # 彩色控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))
        
        # 彩色格式
        color_formatter = colorlog.ColoredFormatter(
            '%(log_color)s[%(asctime)s] [%(levelname)s]%(reset)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(color_formatter)
        self.logger.addHandler(console_handler)
        
        # 文件输出
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, log_level))
            file_formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def get_logger(self):
        """获取logger实例"""
        if self.logger is None:
            self.setup()
        return self.logger


def load_env(env_path: Optional[str] = None):
    """
    加载 .env 环境变量文件
    
    Args:
        env_path: .env 文件路径，默认为项目根目录的 .env
    """
    if env_path is None:
        # 尝试多个可能的位置（优先级从高到低）
        possible_paths = [
            ".env",  # 当前工作目录
            os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),  # 脚本所在目录
        ]
        # 如果设置了 HERMIT_INSTALL_PATH 环境变量，也尝试该路径
        install_path = os.getenv("HERMIT_INSTALL_PATH")
        if install_path:
            possible_paths.append(os.path.join(install_path, ".env"))

        for path in possible_paths:
            if os.path.exists(path):
                env_path = path
                break
    
    if env_path and os.path.exists(env_path):
        load_dotenv(env_path)
        return True
    return False


def get_config() -> Dict[str, Any]:
    """
    从环境变量加载配置（替代 config.yaml）
    
    Returns:
        配置字典
    """
    # 确保加载.env文件
    load_env()
    
    def get_env(key: str, default=None):
        """辅助函数：获取环境变量"""
        return os.getenv(key, default)
    
    def get_env_bool(key: str, default=False) -> bool:
        """辅助函数：获取布尔值环境变量"""
        val = os.getenv(key, str(default)).lower()
        return val in ('true', '1', 'yes', 'on')
    
    def get_env_int(key: str, default=0) -> int:
        """辅助函数：获取整数环境变量"""
        try:
            return int(os.getenv(key, default))
        except:
            return default
    
    # 构建配置字典
    install_path = get_env('HERMIT_INSTALL_PATH', '/root/hermit_crab')
    
    return {
        'base': {
            'install_path': install_path,
            'log_level': get_env('HERMIT_LOG_LEVEL', 'INFO'),
            'current_domain': get_env('HERMIT_CURRENT_DOMAIN', ''),
        },
        'lifecycle': {
            'total_days': get_env_int('HERMIT_TOTAL_DAYS', 15),
            'migrate_threshold_days': get_env_int('HERMIT_MIGRATE_THRESHOLD', 5),
            'minimum_gain_days': get_env_int('HERMIT_MINIMUM_GAIN_DAYS', 1),
            'check_interval': get_env_int('HERMIT_CHECK_INTERVAL', 3600),
        },
        'github': {
            'enabled': get_env_bool('HERMIT_GITHUB_ENABLED', True),
            'repo': get_env('HERMIT_GITHUB_REPO', ''),
            'token_env': 'HERMIT_GITHUB_TOKEN',
            'nodes_file': get_env('HERMIT_GITHUB_NODES_FILE', 'nodes.json'),
            'local_cache': f"{install_path}/data/nodes.json",
        },
        'cloudflare': {
            'enabled': get_env_bool('HERMIT_CF_ENABLED', True),
            'zone_id': get_env('HERMIT_CF_ZONE_ID', ''),
            'api_token_env': 'HERMIT_CF_TOKEN',
            'domain': get_env('HERMIT_CF_DOMAIN', ''),
            'ttl': get_env_int('HERMIT_CF_TTL', 120),
        },
        'security': {
            'ssh_key_path': get_env('HERMIT_SSH_KEY_PATH', '/root/.ssh/hermit_crab_id_rsa'),
            'ssh_user': get_env('HERMIT_SSH_USER', 'root'),
            'use_password': True,
        },
        'migration': {
            'ssh_timeout': get_env_int('HERMIT_SSH_TIMEOUT', 30),
            'max_retries': get_env_int('HERMIT_MAX_RETRIES', 3),
            'retry_interval': get_env_int('HERMIT_RETRY_INTERVAL', 300),
        },
        'rsync': {
            'bandwidth_limit': get_env_int('HERMIT_RSYNC_BANDWIDTH_LIMIT', 0),
            'timeout': get_env_int('HERMIT_RSYNC_TIMEOUT', 7200),
            'exclude_file': f"{install_path}/config/exclude_list.txt",
            'extra_args': get_env('HERMIT_RSYNC_EXTRA_ARGS', '-aAXvzP --delete --numeric-ids'),
        },
        'feedback': {
            'startup_wait': get_env_int('HERMIT_STARTUP_WAIT', 120),
            'max_retry': 10,
            'retry_interval': 300,
        },
        'notification': {
            'enabled': get_env_bool('HERMIT_NOTIFICATION_ENABLED', False),
            'resend_api_key': get_env('HERMIT_RESEND_API_KEY', ''),
            'from_email': get_env('HERMIT_NOTIFICATION_FROM', ''),
            'to_emails': [
                email.strip()
                for email in get_env('HERMIT_NOTIFICATION_TO', '').split(',')
                if email.strip()
            ],
        },
        'debug': {
            'enabled': get_env_bool('HERMIT_DEBUG', False),
            'dry_run': get_env_bool('HERMIT_DRY_RUN', False),
            'skip_reboot': get_env_bool('HERMIT_SKIP_REBOOT', False),
        },
    }


def get_current_ip() -> str:
    """
    获取当前服务器的公网IP
    
    Returns:
        IP地址字符串
    """
    try:
        # 尝试通过外部服务获取公网IP
        result = subprocess.run(
            ['curl', '-s', 'ifconfig.me'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    
    try:
        # 备用方法：获取本地IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def get_hostname() -> str:
    """获取主机名"""
    return socket.gethostname()


def run_command(cmd: str, timeout: int = 300, shell: bool = True) -> tuple:
    """
    执行shell命令
    
    Args:
        cmd: 命令字符串
        timeout: 超时时间（秒）
        shell: 是否使用shell执行
        
    Returns:
        (returncode, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)


def ensure_directory(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def get_env_variable(var_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    获取环境变量
    
    Args:
        var_name: 环境变量名
        default: 默认值
        
    Returns:
        环境变量值或默认值
    """
    return os.environ.get(var_name, default)


def calculate_days_remaining(added_date: str, total_days: int) -> int:
    """
    计算剩余天数
    
    Args:
        added_date: 添加日期字符串 (YYYY-MM-DD)
        total_days: 服务器总生命周期（天）
        
    Returns:
        剩余天数
    """
    try:
        from datetime import timedelta
        added = datetime.strptime(added_date, "%Y-%m-%d")
        expire = added + timedelta(days=total_days)
        now = datetime.now()
        delta = expire - now
        return delta.days
    except Exception as e:
        raise ValueError(f"日期格式错误: {added_date}, 错误: {e}")


def format_date(date_obj: datetime = None) -> str:
    """
    格式化日期为YYYY-MM-DD
    
    Args:
        date_obj: datetime对象，默认为当前时间
        
    Returns:
        格式化的日期字符串
    """
    if date_obj is None:
        date_obj = datetime.now()
    return date_obj.strftime("%Y-%m-%d")


def format_datetime(date_obj: datetime = None) -> str:
    """
    格式化日期时间为ISO格式
    
    Args:
        date_obj: datetime对象，默认为当前时间
        
    Returns:
        格式化的日期时间字符串
    """
    if date_obj is None:
        date_obj = datetime.now()
    return date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")


def check_command_exists(command: str) -> bool:
    """
    检查命令是否存在
    
    Args:
        command: 命令名称
        
    Returns:
        是否存在
    """
    result = subprocess.run(
        f"which {command}",
        shell=True,
        capture_output=True
    )
    return result.returncode == 0


def install_package(package: str) -> bool:
    """
    安装系统包
    
    Args:
        package: 包名
        
    Returns:
        是否成功
    """
    logger = Logger().get_logger()
    logger.info(f"正在安装 {package}...")
    
    result = subprocess.run(
        f"apt-get install -y {package}",
        shell=True,
        capture_output=True
    )
    
    if result.returncode == 0:
        logger.info(f"{package} 安装成功")
        return True
    else:
        logger.error(f"{package} 安装失败: {result.stderr.decode()}")
        return False


def get_ssh_password(target: str = None) -> Optional[str]:
    """
    获取SSH密码
    
    支持三种方式：
    1. 通用密码：HERMIT_SSH_PASSWORD=common_password
    2. 映射密码：HERMIT_SSH_PASSWORD=ip1:pass1|ip2:pass2
    3. 混合模式：HERMIT_SSH_PASSWORD=default_pass + HERMIT_SSH_PASSWORD_MAP=ip1:pass1
    
    Args:
        target: 目标服务器IP或域名
        
    Returns:
        SSH密码，未找到返回None
    """
    # 方式1: 先尝试从 HERMIT_SSH_PASSWORD_MAP 获取特定服务器密码
    password_map = get_env_variable('HERMIT_SSH_PASSWORD_MAP')
    if password_map and target:
        for mapping in password_map.split('|'):
            if ':' in mapping:
                host, password = mapping.split(':', 1)
                if host.strip() == target.strip():
                    return password
    
    # 方式2: 从 HERMIT_SSH_PASSWORD 获取
    password_env = get_env_variable('HERMIT_SSH_PASSWORD')
    if password_env:
        # 检查是否为映射格式（包含 | 或 :）
        if '|' in password_env and target:
            # 映射格式：ip1:pass1|ip2:pass2
            for mapping in password_env.split('|'):
                if ':' in mapping:
                    host, password = mapping.split(':', 1)
                    if host.strip() == target.strip():
                        return password
            # 未找到匹配，返回None（不使用默认密码）
            return None
        else:
            # 通用密码格式
            return password_env
    
    return None


def parse_password_map(password_str: str) -> Dict[str, str]:
    """
    解析密码映射字符串
    
    Args:
        password_str: 密码映射字符串，格式：ip1:pass1|ip2:pass2
        
    Returns:
        密码字典
    """
    password_map = {}
    if password_str:
        for mapping in password_str.split('|'):
            if ':' in mapping:
                host, password = mapping.split(':', 1)
                password_map[host.strip()] = password
    return password_map

