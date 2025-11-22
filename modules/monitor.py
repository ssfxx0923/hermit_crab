"""
监控模块
负责监控本机剩余时间和系统状态
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
from .utils import Logger, calculate_days_remaining, format_date, get_current_ip


class Monitor:
    """服务器生命周期监控器"""
    
    def __init__(self, config: Dict):
        """
        初始化监控器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = Logger().get_logger()
        self.data_dir = os.path.join(config['base']['install_path'], 'data')
        self.lifecycle_file = os.path.join(self.data_dir, 'lifecycle.json')
        
        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)
    
    def initialize_lifecycle(self) -> Dict:
        """
        初始化生命周期信息
        
        系统自动记录当前时间作为添加日期
        
        Returns:
            生命周期信息字典
        """
        # 系统自动记录当前时间
        added_date = format_date()
        
        # 只存储添加日期，过期日期通过 added_date + total_days 自动计算
        total_days = self.config['lifecycle']['total_days']
        
        lifecycle_info = {
            'added_date': added_date,
            'total_days': total_days,
            'current_ip': get_current_ip(),
            'current_domain': self.config['base'].get('current_domain', ''),
            'initialized_at': datetime.now().isoformat(),
            'migration_history': []
        }
        
        # 保存到文件
        with open(self.lifecycle_file, 'w', encoding='utf-8') as f:
            json.dump(lifecycle_info, f, indent=2, ensure_ascii=False)
        
        # 计算过期日期用于日志显示
        from datetime import timedelta
        added = datetime.strptime(added_date, "%Y-%m-%d")
        expire = added + timedelta(days=total_days)
        
        self.logger.info(f"生命周期已初始化: {added_date} -> {format_date(expire)} ({total_days}天)")
        return lifecycle_info
    
    def load_lifecycle(self) -> Optional[Dict]:
        """
        加载生命周期信息
        
        Returns:
            生命周期信息字典，如果不存在则返回None
        """
        if not os.path.exists(self.lifecycle_file):
            self.logger.warning("生命周期文件不存在，需要初始化")
            return None
        
        try:
            with open(self.lifecycle_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"加载生命周期文件失败: {e}")
            return None
    
    def get_remaining_days(self) -> int:
        """
        获取剩余天数
        
        Returns:
            剩余天数，如果未初始化返回-1
        """
        lifecycle = self.load_lifecycle()
        if lifecycle is None:
            return -1
        
        try:
            total_days = lifecycle.get('total_days', self.config['lifecycle']['total_days'])
            return calculate_days_remaining(lifecycle['added_date'], total_days)
        except Exception as e:
            self.logger.error(f"计算剩余天数失败: {e}")
            return -1
    
    def should_migrate(self) -> bool:
        """
        判断是否应该迁移
        
        Returns:
            是否需要迁移
        """
        remaining = self.get_remaining_days()
        
        if remaining < 0:
            self.logger.error("生命周期未初始化或已过期")
            return False
        
        threshold = self.config['lifecycle']['migrate_threshold_days']
        
        if remaining < threshold:
            self.logger.warning(f"剩余时间 {remaining} 天，低于阈值 {threshold} 天，需要迁移！")
            return True
        else:
            self.logger.info(f"剩余时间 {remaining} 天，暂不需要迁移")
            return False
    
    def add_migration_record(self, target_server: Dict):
        """
        添加迁移记录
        
        Args:
            target_server: 目标服务器信息
        """
        lifecycle = self.load_lifecycle()
        if lifecycle is None:
            self.logger.error("无法添加迁移记录：生命周期未初始化")
            return
        
        record = {
            'timestamp': datetime.now().isoformat(),
            'target_ip': target_server.get('ip'),
            'remaining_days': self.get_remaining_days()
        }
        
        lifecycle['migration_history'].append(record)
        
        # 保存
        with open(self.lifecycle_file, 'w', encoding='utf-8') as f:
            json.dump(lifecycle, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"迁移记录已添加: {target_server.get('ip')}")
    
    def get_status(self) -> Dict:
        """
        获取当前状态摘要
        
        Returns:
            状态信息字典
        """
        lifecycle = self.load_lifecycle()
        
        if lifecycle is None:
            return {
                'initialized': False,
                'remaining_days': -1,
                'should_migrate': False,
                'status': 'NOT_INITIALIZED'
            }
        
        remaining = self.get_remaining_days()
        should_migrate = self.should_migrate()
        
        # 判断状态
        if remaining < 0:
            status = 'EXPIRED'
        elif should_migrate:
            status = 'CRITICAL'
        elif remaining < 10:
            status = 'WARNING'
        else:
            status = 'HEALTHY'
        
        # 计算过期日期用于显示
        from datetime import timedelta
        added = datetime.strptime(lifecycle['added_date'], "%Y-%m-%d")
        total_days = lifecycle.get('total_days', self.config['lifecycle']['total_days'])
        expire = added + timedelta(days=total_days)
        
        return {
            'initialized': True,
            'added_date': lifecycle['added_date'],
            'expire_date': format_date(expire),  # 仅用于显示
            'remaining_days': remaining,
            'should_migrate': should_migrate,
            'status': status,
            'current_ip': lifecycle.get('current_ip'),
            'current_domain': lifecycle.get('current_domain'),
            'migration_count': len(lifecycle.get('migration_history', []))
        }
    
    def display_status(self):
        """在控制台显示状态"""
        status = self.get_status()
        
        self.logger.info("=" * 60)
        self.logger.info("Hermit Crab 服务器状态")
        self.logger.info("=" * 60)
        
        if not status['initialized']:
            self.logger.error("⚠️  生命周期未初始化")
            return
        
        # 状态图标
        status_icon = {
            'HEALTHY': '✅',
            'WARNING': '⚠️ ',
            'CRITICAL': '🚨',
            'EXPIRED': '💀'
        }
        
        icon = status_icon.get(status['status'], '❓')
        
        self.logger.info(f"状态: {icon} {status['status']}")
        self.logger.info(f"当前IP: {status.get('current_ip')}")
        self.logger.info(f"当前域名: {status.get('current_domain')}")
        self.logger.info(f"添加日期: {status['added_date']}")
        self.logger.info(f"过期日期: {status['expire_date']}")
        self.logger.info(f"剩余天数: {status['remaining_days']} 天")
        self.logger.info(f"迁移次数: {status['migration_count']}")
        self.logger.info(f"需要迁移: {'是' if status['should_migrate'] else '否'}")
        self.logger.info("=" * 60)

