"""
CloudFlare API模块
负责更新DNS解析记录
"""

import requests
from typing import Dict, Optional
from .utils import Logger, get_env_variable


class CloudFlareAPI:
    """CloudFlare DNS管理器"""
    
    def __init__(self, config: Dict):
        """
        初始化CloudFlare API
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = Logger().get_logger()
        self.enabled = config['cloudflare']['enabled']
        
        if not self.enabled:
            self.logger.warning("CloudFlare DNS更新未启用")
            self.api_token = None
            return
        
        # 获取API Token
        token_env = config['cloudflare']['api_token_env']
        self.api_token = get_env_variable(token_env)
        
        if not self.api_token:
            self.logger.warning(f"CloudFlare API Token未设置 (环境变量: {token_env})")
            return
        
        self.zone_id = config['cloudflare']['zone_id']
        self.domain = config['cloudflare']['domain']
        self.ttl = config['cloudflare'].get('ttl', 120)
        
        # API基础URL
        self.base_url = "https://api.cloudflare.com/client/v4"
        
        # 请求头
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        self.logger.info("CloudFlare API已初始化")
    
    def is_available(self) -> bool:
        """
        检查CloudFlare是否可用
        
        Returns:
            是否可用
        """
        return self.enabled and self.api_token is not None
    
    def get_dns_record(self, subdomain: str) -> Optional[Dict]:
        """
        获取DNS记录
        
        Args:
            subdomain: 子域名（如 server-1）
            
        Returns:
            DNS记录信息，失败返回None
        """
        if not self.is_available():
            self.logger.warning("CloudFlare不可用")
            return None
        
        try:
            full_domain = f"{subdomain}.{self.domain}"
            
            url = f"{self.base_url}/zones/{self.zone_id}/dns_records"
            params = {
                "name": full_domain,
                "type": "A"
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success') and data.get('result'):
                record = data['result'][0]
                self.logger.info(f"找到DNS记录: {full_domain} -> {record['content']}")
                return record
            else:
                self.logger.warning(f"DNS记录不存在: {full_domain}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"获取DNS记录失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"获取DNS记录异常: {e}")
            return None
    
    def create_dns_record(self, subdomain: str, ip: str) -> bool:
        """
        创建DNS A记录
        
        Args:
            subdomain: 子域名
            ip: IP地址
            
        Returns:
            是否成功
        """
        if not self.is_available():
            return False
        
        try:
            full_domain = f"{subdomain}.{self.domain}"
            
            url = f"{self.base_url}/zones/{self.zone_id}/dns_records"
            
            payload = {
                "type": "A",
                "name": full_domain,
                "content": ip,
                "ttl": self.ttl,
                "proxied": False
            }
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success'):
                self.logger.info(f"✅ DNS记录已创建: {full_domain} -> {ip}")
                return True
            else:
                errors = data.get('errors', [])
                self.logger.error(f"创建DNS记录失败: {errors}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"创建DNS记录失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"创建DNS记录异常: {e}")
            return False
    
    def update_dns_record(self, subdomain: str, new_ip: str) -> bool:
        """
        更新DNS A记录
        
        Args:
            subdomain: 子域名
            new_ip: 新的IP地址
            
        Returns:
            是否成功
        """
        if not self.is_available():
            return False
        
        try:
            # 先获取现有记录
            record = self.get_dns_record(subdomain)
            
            if record is None:
                # 记录不存在，创建新记录
                self.logger.info("DNS记录不存在，创建新记录...")
                return self.create_dns_record(subdomain, new_ip)
            
            # 检查IP是否相同
            current_ip = record['content']
            if current_ip == new_ip:
                self.logger.info(f"DNS记录IP未变化: {new_ip}")
                return True
            
            # 更新记录
            record_id = record['id']
            full_domain = f"{subdomain}.{self.domain}"
            
            url = f"{self.base_url}/zones/{self.zone_id}/dns_records/{record_id}"
            
            payload = {
                "type": "A",
                "name": full_domain,
                "content": new_ip,
                "ttl": self.ttl,
                "proxied": False
            }
            
            response = requests.put(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success'):
                self.logger.info(f"✅ DNS记录已更新: {full_domain} {current_ip} -> {new_ip}")
                return True
            else:
                errors = data.get('errors', [])
                self.logger.error(f"更新DNS记录失败: {errors}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"更新DNS记录失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"更新DNS记录异常: {e}")
            return False
    
    def delete_dns_record(self, subdomain: str) -> bool:
        """
        删除DNS记录
        
        Args:
            subdomain: 子域名
            
        Returns:
            是否成功
        """
        if not self.is_available():
            return False
        
        try:
            record = self.get_dns_record(subdomain)
            
            if record is None:
                self.logger.warning(f"DNS记录不存在: {subdomain}")
                return True
            
            record_id = record['id']
            url = f"{self.base_url}/zones/{self.zone_id}/dns_records/{record_id}"
            
            response = requests.delete(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success'):
                self.logger.info(f"✅ DNS记录已删除: {subdomain}")
                return True
            else:
                errors = data.get('errors', [])
                self.logger.error(f"删除DNS记录失败: {errors}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"删除DNS记录失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"删除DNS记录异常: {e}")
            return False
    
    def update_domain_for_migration(self, old_subdomain: str, new_ip: str) -> bool:
        """
        迁移时更新域名解析
        
        Args:
            old_subdomain: 原域名（如 a）
            new_ip: 新服务器IP
            
        Returns:
            是否成功
        """
        self.logger.info(f"更新域名解析: {old_subdomain}.{self.domain} -> {new_ip}")
        return self.update_dns_record(old_subdomain, new_ip)

