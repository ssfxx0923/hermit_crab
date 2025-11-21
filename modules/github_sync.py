"""
GitHub同步模块
负责与GitHub仓库同步服务器列表
"""

import json
import base64
from typing import Dict, Optional
from github import Github, GithubException
from .utils import Logger, get_env_variable, format_datetime


class GitHubSync:
    """GitHub同步管理器"""
    
    def __init__(self, config: Dict):
        """
        初始化GitHub同步器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = Logger().get_logger()
        self.enabled = config['github']['enabled']
        
        if not self.enabled:
            self.logger.warning("GitHub同步未启用")
            self.github = None
            self.repo = None
            return
        
        # 获取GitHub Token
        token_env = config['github']['token_env']
        self.token = get_env_variable(token_env)
        
        if not self.token:
            self.logger.warning(f"GitHub Token未设置 (环境变量: {token_env})")
            self.github = None
            self.repo = None
            return
        
        try:
            self.github = Github(self.token)
            repo_name = config['github']['repo']
            self.repo = self.github.get_repo(repo_name)
            self.nodes_file = config['github']['nodes_file']
            self.logger.info(f"GitHub仓库已连接: {repo_name}")
        except GithubException as e:
            self.logger.error(f"GitHub连接失败: {e}")
            self.github = None
            self.repo = None
    
    def is_available(self) -> bool:
        """
        检查GitHub是否可用
        
        Returns:
            是否可用
        """
        return self.enabled and self.github is not None and self.repo is not None
    
    def pull_nodes(self) -> Optional[Dict]:
        """
        从GitHub拉取服务器列表
        
        Returns:
            服务器列表字典，失败返回None
        """
        if not self.is_available():
            self.logger.warning("GitHub不可用，无法拉取")
            return None
        
        try:
            self.logger.info(f"从GitHub拉取: {self.nodes_file}")
            
            # 获取文件内容
            file_content = self.repo.get_contents(self.nodes_file)
            content = file_content.decoded_content.decode('utf-8')
            
            nodes_data = json.loads(content)
            self.logger.info(f"✅ 成功拉取服务器列表 ({len(nodes_data.get('servers', []))} 个服务器)")
            
            return nodes_data
            
        except GithubException as e:
            if e.status == 404:
                self.logger.warning(f"文件不存在: {self.nodes_file}")
            else:
                self.logger.error(f"GitHub拉取失败: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"拉取异常: {e}")
            return None
    
    def push_nodes(self, nodes_data: Dict, commit_message: Optional[str] = None) -> bool:
        """
        推送服务器列表到GitHub
        
        Args:
            nodes_data: 服务器列表字典
            commit_message: 提交信息
            
        Returns:
            是否成功
        """
        if not self.is_available():
            self.logger.warning("GitHub不可用，无法推送")
            return False
        
        try:
            if commit_message is None:
                commit_message = f"Update nodes.json at {format_datetime()}"
            
            self.logger.info("推送服务器列表到GitHub...")
            
            # 更新时间戳
            nodes_data['last_updated'] = format_datetime()
            
            # 转换为JSON
            content = json.dumps(nodes_data, indent=2, ensure_ascii=False)
            
            # 检查文件是否存在
            try:
                file_content = self.repo.get_contents(self.nodes_file)
                # 文件存在，更新
                self.repo.update_file(
                    path=self.nodes_file,
                    message=commit_message,
                    content=content,
                    sha=file_content.sha
                )
                self.logger.info("✅ 服务器列表已更新到GitHub")
            except GithubException as e:
                if e.status == 404:
                    # 文件不存在，创建
                    self.repo.create_file(
                        path=self.nodes_file,
                        message=commit_message,
                        content=content
                    )
                    self.logger.info("✅ 服务器列表已创建到GitHub")
                else:
                    raise
            
            return True
            
        except GithubException as e:
            self.logger.error(f"GitHub推送失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"推送异常: {e}")
            return False
    
    def update_server_status(self, server_id: str, status: str, **kwargs) -> bool:
        """
        更新单个服务器状态并推送到GitHub
        
        Args:
            server_id: 服务器ID或域名
            status: 新状态
            **kwargs: 其他要更新的字段
            
        Returns:
            是否成功
        """
        if not self.is_available():
            self.logger.warning("GitHub不可用")
            return False
        
        # 先拉取最新数据
        nodes_data = self.pull_nodes()
        if nodes_data is None:
            return False
        
        # 查找并更新服务器
        servers = nodes_data.get('servers', [])
        updated = False
        
        for server in servers:
            if server.get('id') == server_id or server.get('domain') == server_id:
                server['status'] = status
                server['last_heartbeat'] = format_datetime()
                
                # 更新其他字段
                for key, value in kwargs.items():
                    server[key] = value
                
                updated = True
                self.logger.info(f"服务器 {server_id} 状态已更新: {status}")
                break
        
        if not updated:
            self.logger.warning(f"未找到服务器: {server_id}")
            return False
        
        # 推送更新
        commit_msg = f"Update server {server_id} status to {status}"
        return self.push_nodes(nodes_data, commit_msg)
    
    def acquire_lock(self, server_id: str, lock_holder: str) -> bool:
        """
        获取服务器锁（防止并发迁移到同一服务器）
        
        使用GitHub API的原子性来实现分布式锁
        
        Args:
            server_id: 服务器ID
            lock_holder: 锁持有者标识
            
        Returns:
            是否成功获取锁
        """
        if not self.is_available():
            self.logger.warning("GitHub不可用，无法获取锁")
            return False
        
        try:
            # 拉取最新数据
            nodes_data = self.pull_nodes()
            if nodes_data is None:
                return False
            
            # 查找服务器
            servers = nodes_data.get('servers', [])
            target_server = None
            
            for server in servers:
                if server.get('id') == server_id or server.get('domain') == server_id:
                    target_server = server
                    break
            
            if target_server is None:
                self.logger.error(f"服务器不存在: {server_id}")
                return False
            
            # 检查锁状态
            current_status = target_server.get('status')
            
            if current_status == 'transferring':
                self.logger.warning(f"服务器 {server_id} 已被锁定")
                return False
            
            # 尝试获取锁
            target_server['status'] = 'transferring'
            target_server['lock_holder'] = lock_holder
            target_server['lock_time'] = format_datetime()
            
            # 推送更新
            commit_msg = f"Lock server {server_id} for {lock_holder}"
            
            if self.push_nodes(nodes_data, commit_msg):
                self.logger.info(f"✅ 成功获取服务器锁: {server_id}")
                return True
            else:
                self.logger.error("推送锁定状态失败")
                return False
                
        except Exception as e:
            self.logger.error(f"获取锁异常: {e}")
            return False
    
    def release_lock(self, server_id: str, new_status: str = 'active') -> bool:
        """
        释放服务器锁
        
        Args:
            server_id: 服务器ID
            new_status: 释放后的新状态
            
        Returns:
            是否成功
        """
        if not self.is_available():
            return False
        
        try:
            nodes_data = self.pull_nodes()
            if nodes_data is None:
                return False
            
            servers = nodes_data.get('servers', [])
            
            for server in servers:
                if server.get('id') == server_id or server.get('domain') == server_id:
                    server['status'] = new_status
                    server.pop('lock_holder', None)
                    server.pop('lock_time', None)
                    
                    commit_msg = f"Release lock on server {server_id}"
                    
                    if self.push_nodes(nodes_data, commit_msg):
                        self.logger.info(f"✅ 已释放服务器锁: {server_id}")
                        return True
                    break
            
            return False
            
        except Exception as e:
            self.logger.error(f"释放锁异常: {e}")
            return False

