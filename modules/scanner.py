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
    
    def get_available_servers(self, exclude_status: List[str] = None) -> List[Dict]:
        """
        获取可用服务器列表
        
        Args:
            exclude_status: 需要排除的状态列表
            
        Returns:
            可用服务器列表
        """
        if exclude_status is None:
            exclude_status = ['transferring', 'dead']
        
        nodes_data = self.load_nodes()
        servers = nodes_data.get('servers', [])
        
        available = []
        for server in servers:
            # 排除特定状态
            if server.get('status') in exclude_status:
                continue
            
            # 检查是否过期
            try:
                remaining = calculate_days_remaining(server['expire_date'])
                if remaining < 0:
                    self.logger.warning(f"服务器 {server.get('domain')} 已过期")
                    continue
                
                # 添加剩余天数信息
                server['remaining_days'] = remaining
                available.append(server)
            except Exception as e:
                self.logger.error(f"处理服务器 {server.get('id')} 时出错: {e}")
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
                f"选择高优先级服务器: {target.get('domain')} "
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
                f"选择低优先级服务器: {target.get('domain')} "
                f"(剩余 {target['remaining_days']} 天)"
            )
            return target
        
        # 没有合适的服务器
        self.logger.warning(
            f"没有找到合适的目标服务器 "
            f"(当前剩余 {current_remaining_days} 天)"
        )
        return None
    
    def update_server_status(self, server_id: str, status: str, **kwargs):
        """
        更新服务器状态
        
        Args:
            server_id: 服务器ID
            status: 新状态
            **kwargs: 其他要更新的字段
        """
        nodes_data = self.load_nodes()
        servers = nodes_data.get('servers', [])
        
        updated = False
        for server in servers:
            if server.get('id') == server_id or server.get('domain') == server_id:
                server['status'] = status
                server['last_heartbeat'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                
                # 更新其他字段
                for key, value in kwargs.items():
                    server[key] = value
                
                updated = True
                self.logger.info(f"服务器 {server_id} 状态已更新为: {status}")
                break
        
        if not updated:
            self.logger.warning(f"未找到服务器: {server_id}")
            return
        
        self.save_nodes(nodes_data)
    
    def add_server(self, ip: str, domain: str, added_date: str, expire_date: str, 
                   status: str = "idle", **kwargs) -> bool:
        """
        添加新服务器
        
        Args:
            ip: IP地址
            domain: 域名
            added_date: 添加日期
            expire_date: 过期日期
            status: 状态
            **kwargs: 其他字段
            
        Returns:
            是否成功
        """
        nodes_data = self.load_nodes()
        servers = nodes_data.get('servers', [])
        
        # 检查是否已存在
        for server in servers:
            if server.get('ip') == ip or server.get('domain') == domain:
                self.logger.warning(f"服务器已存在: {domain}")
                return False
        
        # 生成ID
        server_id = f"server-{len(servers) + 1:03d}"
        
        # 创建新服务器记录
        new_server = {
            'id': server_id,
            'ip': ip,
            'domain': domain,
            'added_date': added_date,
            'expire_date': expire_date,
            'status': status,
            'last_heartbeat': None,
            'notes': kwargs.get('notes', '')
        }
        
        # 添加其他字段
        for key, value in kwargs.items():
            if key not in new_server:
                new_server[key] = value
        
        servers.append(new_server)
        nodes_data['servers'] = servers
        
        self.save_nodes(nodes_data)
        self.logger.info(f"已添加新服务器: {domain} ({ip})")
        
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
        self.logger.info(f"{'ID':<15} {'域名':<25} {'IP':<15} {'剩余天数':<10} {'状态':<10}")
        self.logger.info("=" * 80)
        
        for server in servers:
            if filter_status and server.get('status') != filter_status:
                continue
            
            try:
                remaining = calculate_days_remaining(server['expire_date'])
            except:
                remaining = -999
            
            self.logger.info(
                f"{server.get('id', 'N/A'):<15} "
                f"{server.get('domain', 'N/A'):<25} "
                f"{server.get('ip', 'N/A'):<15} "
                f"{remaining:<10} "
                f"{server.get('status', 'N/A'):<10}"
            )
        
        self.logger.info("=" * 80)

