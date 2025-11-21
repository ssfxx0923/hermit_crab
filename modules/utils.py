"""
工具函数模块
提供日志、配置加载、网络检测等通用功能
"""

import os
import sys
import yaml
import logging
import socket
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional
import colorlog


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


def load_config(config_path: str = "/opt/hermit_crab/config.yaml") -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件未找到: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"配置文件格式错误: {e}")


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


def calculate_days_remaining(expire_date: str) -> int:
    """
    计算剩余天数
    
    Args:
        expire_date: 过期日期字符串 (YYYY-MM-DD)
        
    Returns:
        剩余天数
    """
    try:
        expire = datetime.strptime(expire_date, "%Y-%m-%d")
        now = datetime.now()
        delta = expire - now
        return delta.days
    except Exception as e:
        raise ValueError(f"日期格式错误: {expire_date}, 错误: {e}")


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

