"""
Hermit Crab 邮件通知模块
使用 Resend API 发送电子邮件通知
"""

import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Any


class ResendNotifier:
    """Resend API 邮件通知器"""

    def __init__(self, config: dict):
        """
        初始化通知器

        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Resend 配置
        self.enabled = config.get('notification', {}).get('enabled', False)
        self.api_key = config.get('notification', {}).get('resend_api_key', '')
        self.from_email = config.get('notification', {}).get('from_email', '')
        self.to_emails = config.get('notification', {}).get('to_emails', [])

        # Resend API endpoint
        self.api_url = "https://api.resend.com/emails"

        if self.enabled and not self.api_key:
            self.logger.warning("邮件通知已启用但未配置 API Key")
            self.enabled = False

        if self.enabled and not self.to_emails:
            self.logger.warning("邮件通知已启用但未配置收件人")
            self.enabled = False

    def is_available(self) -> bool:
        """检查通知功能是否可用"""
        return self.enabled and bool(self.api_key) and bool(self.to_emails)

    def send_email(self, subject: str, html_content: str, to_emails: Optional[list] = None) -> bool:
        """
        发送邮件

        Args:
            subject: 邮件主题
            html_content: HTML 内容
            to_emails: 收件人列表（可选，默认使用配置中的）

        Returns:
            是否发送成功
        """
        if not self.is_available():
            self.logger.debug("邮件通知未启用，跳过发送")
            return False

        recipients = to_emails or self.to_emails

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "from": self.from_email,
                "to": recipients,
                "subject": subject,
                "html": html_content
            }

            self.logger.debug(f"发送邮件: {subject} -> {recipients}")

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                self.logger.info(f"✅ 邮件发送成功: {subject}")
                return True
            else:
                self.logger.error(f"❌ 邮件发送失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"发送邮件异常: {e}")
            return False

    # ========================================
    # 邮件模板
    # ========================================

    def _get_base_template(self, title: str, content: str, status_color: str = "#3b82f6") -> str:
        """基础邮件模板"""
        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0; padding:20px; font-family:system-ui,-apple-system,sans-serif; background:#f5f5f5;">
  <div style="max-width:500px; margin:0 auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
    <div style="background:{status_color}; padding:20px; color:#fff;">
      <div style="font-size:20px; font-weight:600;">🦀 Hermit Crab</div>
      <div style="font-size:14px; opacity:0.9; margin-top:4px;">{title}</div>
    </div>
    <div style="padding:24px;">
      {content}
    </div>
    <div style="padding:16px 24px; background:#f9f9f9; color:#666; font-size:12px; border-top:1px solid #eee;">
      {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </div>
  </div>
</body>
</html>"""

    def _format_info(self, data: Dict[str, str]) -> str:
        """格式化信息列表"""
        items = "".join(f'<div style="padding:8px 0; border-bottom:1px solid #eee;"><span style="color:#666;">{k}:</span> <strong>{v}</strong></div>' for k, v in data.items())
        return f'<div style="margin:16px 0;">{items}</div>'

    def _alert_box(self, text: str, color: str = "#3b82f6") -> str:
        """提示框"""
        return f'<div style="margin:16px 0; padding:12px; background:{color}10; border-left:3px solid {color}; border-radius:4px; color:#333;">{text}</div>'

    # ========================================
    # 通知方法
    # ========================================

    def notify_migration_started(self, source_ip: str, target_ip: str, remaining_days: int) -> bool:
        """迁移开始通知"""
        info = {"源服务器": source_ip, "目标服务器": target_ip, "剩余天数": f"{remaining_days} 天"}
        content = f"""
        <p style="color:#333; margin:0 0 16px;">检测到服务器即将到期，正在自动执行迁移。</p>
        {self._format_info(info)}
        {self._alert_box("💡 迁移过程可能需要几分钟到几小时")}
        """
        return self.send_email(f"🔄 迁移开始 - {source_ip} → {target_ip}", self._get_base_template("迁移开始", content, "#3b82f6"))

    def notify_migration_success(self, source_ip: str, target_ip: str,
                                duration_seconds: float, domain: Optional[str] = None) -> bool:
        """迁移成功通知"""
        info = {"源服务器": source_ip, "目标服务器": target_ip, "耗时": f"{duration_seconds / 60:.1f} 分钟"}
        if domain:
            info["域名"] = domain
        content = f"""
        <p style="color:#333; margin:0 0 16px;">服务器迁移已成功完成！</p>
        {self._format_info(info)}
        {self._alert_box("✅ DNS 已更新，服务正常运行", "#10b981")}
        """
        return self.send_email(f"✅ 迁移成功 - {source_ip} → {target_ip}", self._get_base_template("迁移成功", content, "#10b981"))

    def notify_migration_failed(self, source_ip: str, target_ip: Optional[str],
                               error_message: str, stage: str = "未知") -> bool:
        """迁移失败通知"""
        info = {"源服务器": source_ip, "目标服务器": target_ip or "未选择", "失败阶段": stage}
        content = f"""
        <p style="color:#333; margin:0 0 16px;">迁移过程中遇到错误，需要人工处理。</p>
        {self._format_info(info)}
        {self._alert_box(f"❌ {error_message}", "#ef4444")}
        """
        return self.send_email(f"❌ 迁移失败 - {source_ip}", self._get_base_template("迁移失败", content, "#ef4444"))

    def notify_lifecycle_warning(self, server_ip: str, remaining_days: int,
                                total_days: int, domain: Optional[str] = None) -> bool:
        """生命周期警告通知"""
        info = {"服务器": server_ip, "剩余": f"{remaining_days} / {total_days} 天"}
        if domain:
            info["域名"] = domain

        if remaining_days <= 2:
            level, color = "🚨 紧急", "#ef4444"
        elif remaining_days <= 5:
            level, color = "⚠️ 警告", "#f59e0b"
        else:
            level, color = "ℹ️ 提醒", "#3b82f6"

        content = f"""
        <p style="color:#333; margin:0 0 16px;">服务器生命周期即将结束。</p>
        {self._format_info(info)}
        {self._alert_box(f"{level}: 请确认备用服务器已就绪", color)}
        """
        return self.send_email(f"{level} 剩余 {remaining_days} 天 - {server_ip}", self._get_base_template("生命周期警告", content, color))

    def notify_server_added(self, server_ip: str, added_by: str = "系统",
                           notes: str = "", expire_date: Optional[str] = None) -> bool:
        """服务器添加通知"""
        info = {"服务器": server_ip, "添加者": added_by}
        if notes:
            info["备注"] = notes
        if expire_date:
            info["过期时间"] = expire_date
        content = f"""
        <p style="color:#333; margin:0 0 16px;">新服务器已添加到服务器池。</p>
        {self._format_info(info)}
        """
        return self.send_email(f"🆕 新服务器 - {server_ip}", self._get_base_template("服务器添加", content, "#10b981"))

    def notify_ssh_failed(self, server_ip: str, error_message: str, retry_count: int = 0) -> bool:
        """SSH 连接失败通知"""
        info = {"服务器": server_ip, "重试次数": str(retry_count)}
        content = f"""
        <p style="color:#333; margin:0 0 16px;">连接目标服务器失败。</p>
        {self._format_info(info)}
        {self._alert_box(f"❌ {error_message}", "#ef4444")}
        """
        return self.send_email(f"❌ SSH 失败 - {server_ip}", self._get_base_template("SSH 失败", content, "#ef4444"))

    def notify_no_available_servers(self, current_ip: str, remaining_days: int) -> bool:
        """无可用服务器通知"""
        info = {"当前服务器": current_ip, "剩余天数": str(remaining_days)}
        content = f"""
        <p style="color:#333; margin:0 0 16px;">需要迁移但找不到可用的目标服务器。</p>
        {self._format_info(info)}
        {self._alert_box("🚨 请尽快添加新服务器到服务器池", "#ef4444")}
        """
        return self.send_email(f"🚨 无可用服务器 - 剩余 {remaining_days} 天", self._get_base_template("无可用服务器", content, "#ef4444"))
