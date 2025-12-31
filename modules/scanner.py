"""
扫描器模块
负责管理和选择可用服务器
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from .utils import Logger, calculate_days_remaining


class Scanner:
    """服务器列表扫描器"""
    
    def __init__(self, config: Dict):
        """
        初始化扫描器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = Logger().get_logger()
        self.nodes_file = config['github']['local_cache']
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.nodes_file), exist_ok=True)
    
    def load_nodes(self) -> Dict:
        """
        加载服务器列表
        
        Returns:
            服务器列表字典
        """
        if not os.path.exists(self.nodes_file):
            self.logger.warning(f"服务器列表文件不存在: {self.nodes_file}")
            return {'servers': []}
        
        try:
            with open(self.nodes_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"加载服务器列表失败: {e}")
            return {'servers': []}
    
    def save_nodes(self, nodes_data: Dict):
        """
        保存服务器列表
        
        Args:
            nodes_data: 服务器列表字典
        """
        try:
            # 更新时间戳
            nodes_data['last_updated'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            
            with open(self.nodes_file, 'w', encoding='utf-8') as f:
                json.dump(nodes_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info("服务器列表已保存")
        except Exception as e:
            self.logger.error(f"保存服务器列表失败: {e}")
    
    def get_available_servers(self, only_idle: bool = True, exclude_current: bool = True) -> List[Dict]:
        """
        获取可用服务器列表

        Args:
            only_idle: 是否只筛选idle状态的服务器（默认True，更合理）
            exclude_current: 是否排除当前服务器（默认True）

        Returns:
            可用服务器列表
        """
        nodes_data = self.load_nodes()
        servers = nodes_data.get('servers', [])

        # 获取当前服务器IP
        from .utils import get_current_ip
        current_ip = get_current_ip() if exclude_current else None

        available = []
        for server in servers:
            # 排除当前服务器
            if exclude_current and server.get('ip') == current_ip:
                self.logger.debug(f"排除当前服务器: {current_ip}")
                continue

            # 筛选idle状态（更合理的做法）
            server_status = server.get('status', 'idle')
            if only_idle:
                if server_status != 'idle':
                    self.logger.debug(f"跳过非idle服务器: {server['ip']} (状态: {server_status})")
                    continue
            else:
                # 如果不限制只idle，则排除明确不可用的状态
                if server_status in ['transferring', 'dead', 'active']:
                    self.logger.debug(f"跳过不可用服务器: {server['ip']} (状态: {server_status})")
                    continue

            # 检查是否过期
            try:
                # 优先使用服务器自己的 total_days，否则使用默认配置
                total_days = server.get('total_days', self.config['lifecycle']['total_days'])
                remaining = calculate_days_remaining(server['added_date'], total_days)
                if remaining < 0:
                    self.logger.warning(f"服务器 {server['ip']} 已过期")
                    continue

                # 添加剩余天数信息
                server['remaining_days'] = remaining
                available.append(server)
            except Exception as e:
                self.logger.error(f"处理服务器 {server.get('ip')} 时出错: {e}")
                continue

        return available
    
    def select_target_server(self, current_remaining_days: int) -> Optional[Dict]:
        """
        选择目标服务器
        
        选择逻辑：
        1. 优先选择剩余时间 > 5天 的服务器中时间最长的
        2. 如果没有，选择至少比当前服务器多1天的服务器中时间最长的
        
        Args:
            current_remaining_days: 当前服务器剩余天数
            
        Returns:
            选中的服务器信息，如果没有合适的返回None
        """
        threshold = self.config['lifecycle']['migrate_threshold_days']
        min_gain = self.config['lifecycle']['minimum_gain_days']
        
        available = self.get_available_servers()
        
        if not available:
            self.logger.error("没有可用的服务器")
            return None
        
        self.logger.info(f"找到 {len(available)} 个可用服务器")
        
        # 优先级1: 剩余时间 > 5天
        candidates_high = [s for s in available if s['remaining_days'] > threshold]
        
        if candidates_high:
            # 选择时间最长的
            target = max(candidates_high, key=lambda x: x['remaining_days'])
            self.logger.info(
                f"选择高优先级服务器: {target['ip']} "
                f"(剩余 {target['remaining_days']} 天)"
            )
            return target
        
        # 优先级2: 至少比当前多1天
        candidates_low = [
            s for s in available 
            if s['remaining_days'] > (current_remaining_days + min_gain)
        ]
        
        if candidates_low:
            target = max(candidates_low, key=lambda x: x['remaining_days'])
            self.logger.info(
                f"选择低优先级服务器: {target['ip']} "
                f"(剩余 {target['remaining_days']} 天)"
            )
            return target
        
        # 没有合适的服务器
        self.logger.warning(
            f"没有找到合适的目标服务器 "
            f"(当前剩余 {current_remaining_days} 天)"
        )
        return None

    def select_longest_remaining_server(self) -> Optional[Dict]:
        """
        选择剩余时间最长的服务器（用于强制迁移）

        Returns:
            剩余时间最长的服务器信息，如果没有可用服务器返回None
        """
        available = self.get_available_servers()

        if not available:
            self.logger.error("没有可用的服务器")
            return None

        self.logger.info(f"找到 {len(available)} 个可用服务器")

        # 选择剩余时间最长的
        target = max(available, key=lambda x: x['remaining_days'])
        self.logger.info(
            f"✅ 选择剩余时间最长的服务器: {target['ip']} "
            f"(剩余 {target['remaining_days']} 天)"
        )
        return target

    def update_server_status(self, ip: str, status: str, **kwargs):
        """
        更新服务器状态
        
        Args:
            ip: 服务器IP地址
            status: 新状态
            **kwargs: 其他要更新的字段
        """
        nodes_data = self.load_nodes()
        servers = nodes_data.get('servers', [])
        
        updated = False
        for server in servers:
            if server.get('ip') == ip:
                server['status'] = status
                server['last_heartbeat'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                
                # 更新其他字段
                for key, value in kwargs.items():
                    server[key] = value
                
                updated = True
                self.logger.info(f"服务器 {ip} 状态已更新为: {status}")
                break
        
        if not updated:
            self.logger.warning(f"未找到服务器: {ip}")
            return
        
        self.save_nodes(nodes_data)
    
    def add_server(self, ip: str, status: str = "idle", notes: str = "", total_days: int = None) -> bool:
        """
        添加新服务器

        Args:
            ip: IP地址
            status: 状态
            notes: 备注（可选）
            total_days: 服务器生命周期天数（可选，默认使用配置值）

        Returns:
            是否成功
        """
        from .utils import format_date

        nodes_data = self.load_nodes()
        servers = nodes_data.get('servers', [])

        # 检查是否已存在
        for server in servers:
            if server.get('ip') == ip:
                self.logger.warning(f"服务器已存在: {ip}")
                return False

        # 系统自动记录当前时间
        added_date = format_date()

        # 使用指定的 total_days 或默认配置
        if total_days is None:
            total_days = self.config['lifecycle']['total_days']

        # 创建新服务器记录
        new_server = {
            'ip': ip,
            'added_date': added_date,
            'total_days': total_days,
            'status': status,
            'last_heartbeat': None,
            'notes': notes
        }

        servers.append(new_server)
        nodes_data['servers'] = servers

        self.save_nodes(nodes_data)
        self.logger.info(f"已添加新服务器: {ip} (生命周期: {total_days} 天)")

        return True
    
    def remove_server(self, ip: str) -> bool:
        """
        删除服务器

        Args:
            ip: 服务器IP地址

        Returns:
            是否成功删除
        """
        nodes_data = self.load_nodes()
        servers = nodes_data.get('servers', [])

        # 查找并删除服务器
        initial_count = len(servers)
        servers = [s for s in servers if s.get('ip') != ip]

        if len(servers) == initial_count:
            self.logger.warning(f"未找到服务器: {ip}")
            return False

        nodes_data['servers'] = servers
        self.save_nodes(nodes_data)
        self.logger.info(f"✅ 已删除服务器: {ip}")

        return True

    def list_servers(self, filter_status: Optional[str] = None):
        """
        列出所有服务器

        Args:
            filter_status: 过滤特定状态
        """
        nodes_data = self.load_nodes()
        servers = nodes_data.get('servers', [])

        if not servers:
            self.logger.info("服务器列表为空")
            return

        self.logger.info("=" * 80)
        self.logger.info(f"{'IP地址':<18} {'剩余天数':<12} {'状态':<12} {'备注':<30}")
        self.logger.info("=" * 80)

        for server in servers:
            if filter_status and server.get('status') != filter_status:
                continue

            try:
                # 优先使用服务器自己的 total_days
                total_days = server.get('total_days', self.config['lifecycle']['total_days'])
                remaining = calculate_days_remaining(server['added_date'], total_days)
            except:
                remaining = -999

            self.logger.info(
                f"{server.get('ip', 'N/A'):<18} "
                f"{remaining:<12} "
                f"{server.get('status', 'N/A'):<12} "
                f"{server.get('notes', ''):<30}"
            )

        self.logger.info("=" * 80)
