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
        """
        基础邮件模板

        Args:
            title: 标题
            content: 内容（HTML）
            status_color: 状态条颜色
        """
        return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, {status_color} 0%, #1e40af 100%); padding: 30px; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">
                                🦀 Hermit Crab
                            </h1>
                            <p style="margin: 8px 0 0 0; color: #e0e7ff; font-size: 14px;">
                                寄居蟹自动迁移系统
                            </p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="margin: 0 0 20px 0; color: #111827; font-size: 20px; font-weight: 600;">
                                {title}
                            </h2>
                            {content}
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 20px 30px; border-radius: 0 0 8px 8px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; color: #6b7280; font-size: 12px; text-align: center;">
                                此邮件由 Hermit Crab 自动发送 | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    def _create_info_table(self, data: Dict[str, str]) -> str:
        """创建信息表格"""
        rows = ""
        for key, value in data.items():
            rows += f"""
            <tr>
                <td style="padding: 12px; background-color: #f9fafb; border: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 180px;">
                    {key}
                </td>
                <td style="padding: 12px; background-color: #ffffff; border: 1px solid #e5e7eb; color: #111827;">
                    {value}
                </td>
            </tr>
            """

        return f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; margin: 20px 0;">
            {rows}
        </table>
        """

    # ========================================
    # 通知方法
    # ========================================

    def notify_migration_started(self, source_ip: str, target_ip: str, remaining_days: int) -> bool:
        """
        迁移开始通知

        Args:
            source_ip: 源服务器IP
            target_ip: 目标服务器IP
            remaining_days: 源服务器剩余天数
        """
        info = {
            "源服务器": source_ip,
            "目标服务器": target_ip,
            "剩余天数": f"{remaining_days} 天",
            "开始时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "状态": "🔄 迁移中"
        }

        content = f"""
        <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
            Hermit Crab 检测到服务器剩余时间不足，正在自动执行迁移流程。
        </p>

        {self._create_info_table(info)}

        <div style="background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0; color: #1e40af; font-size: 14px;">
                <strong>💡 提示：</strong>迁移过程可能需要几分钟到几小时，具体取决于数据量大小。
            </p>
        </div>
        """

        subject = f"🔄 [Hermit Crab] 迁移开始 - {source_ip} → {target_ip}"
        html = self._get_base_template("迁移流程已启动", content, "#3b82f6")

        return self.send_email(subject, html)

    def notify_migration_success(self, source_ip: str, target_ip: str,
                                duration_seconds: float, domain: Optional[str] = None) -> bool:
        """
        迁移成功通知

        Args:
            source_ip: 源服务器IP
            target_ip: 目标服务器IP
            duration_seconds: 迁移耗时（秒）
            domain: 业务域名
        """
        duration_minutes = duration_seconds / 60

        info = {
            "源服务器": source_ip,
            "目标服务器": target_ip,
            "总耗时": f"{duration_minutes:.1f} 分钟 ({duration_seconds:.0f} 秒)",
            "完成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "状态": "✅ 迁移成功"
        }

        if domain:
            info["业务域名"] = f"{domain} → {target_ip}"

        content = f"""
        <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
            🎉 太棒了！服务器迁移已成功完成，所有服务正在新服务器上运行。
        </p>

        {self._create_info_table(info)}

        <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0; color: #065f46; font-size: 14px;">
                <strong>✅ 迁移完成：</strong>DNS 已更新，新服务器已启动自动监控。
            </p>
        </div>
        """

        subject = f"✅ [Hermit Crab] 迁移成功 - {source_ip} → {target_ip}"
        html = self._get_base_template("迁移成功完成", content, "#10b981")

        return self.send_email(subject, html)

    def notify_migration_failed(self, source_ip: str, target_ip: Optional[str],
                               error_message: str, stage: str = "未知") -> bool:
        """
        迁移失败通知

        Args:
            source_ip: 源服务器IP
            target_ip: 目标服务器IP（可能为空）
            error_message: 错误信息
            stage: 失败阶段
        """
        info = {
            "源服务器": source_ip,
            "目标服务器": target_ip or "未选择",
            "失败阶段": stage,
            "失败时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "状态": "❌ 迁移失败"
        }

        content = f"""
        <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
            ⚠️ 迁移过程中遇到错误，需要人工介入处理。
        </p>

        {self._create_info_table(info)}

        <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0 0 8px 0; color: #991b1b; font-size: 14px; font-weight: 600;">
                ❌ 错误信息：
            </p>
            <pre style="margin: 0; color: #7f1d1d; font-size: 13px; font-family: 'Courier New', monospace; white-space: pre-wrap; word-wrap: break-word;">{error_message}</pre>
        </div>

        <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0; color: #92400e; font-size: 14px;">
                <strong>🔧 建议操作：</strong>请登录服务器查看详细日志，手动排查问题。
            </p>
        </div>
        """

        subject = f"❌ [Hermit Crab] 迁移失败 - {source_ip}"
        html = self._get_base_template("迁移失败", content, "#ef4444")

        return self.send_email(subject, html)

    def notify_lifecycle_warning(self, server_ip: str, remaining_days: int,
                                total_days: int, domain: Optional[str] = None) -> bool:
        """
        生命周期警告通知

        Args:
            server_ip: 服务器IP
            remaining_days: 剩余天数
            total_days: 总天数
            domain: 业务域名
        """
        percentage = (remaining_days / total_days) * 100

        info = {
            "服务器IP": server_ip,
            "剩余天数": f"{remaining_days} 天",
            "总生命周期": f"{total_days} 天",
            "剩余比例": f"{percentage:.1f}%",
            "检查时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if domain:
            info["业务域名"] = domain

        # 根据剩余天数选择警告级别
        if remaining_days <= 2:
            warning_level = "🚨 紧急"
            warning_color = "#ef4444"
            warning_bg = "#fef2f2"
            warning_message = "服务器即将到期，请尽快确认是否有可用的备用服务器！"
        elif remaining_days <= 5:
            warning_level = "⚠️ 警告"
            warning_color = "#f59e0b"
            warning_bg = "#fffbeb"
            warning_message = "服务器剩余时间不足，系统将在检测到合适的目标后自动迁移。"
        else:
            warning_level = "ℹ️ 提醒"
            warning_color = "#3b82f6"
            warning_bg = "#eff6ff"
            warning_message = "服务器剩余时间较少，请提前准备备用服务器。"

        content = f"""
        <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
            Hermit Crab 检测到服务器生命周期即将结束。
        </p>

        {self._create_info_table(info)}

        <div style="background-color: {warning_bg}; border-left: 4px solid {warning_color}; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0; color: {warning_color}; font-size: 14px;">
                <strong>{warning_level}：</strong>{warning_message}
            </p>
        </div>
        """

        subject = f"{warning_level} [Hermit Crab] 服务器剩余 {remaining_days} 天 - {server_ip}"
        html = self._get_base_template("生命周期警告", content, warning_color)

        return self.send_email(subject, html)

    def notify_server_added(self, server_ip: str, added_by: str = "系统",
                           notes: str = "", expire_date: Optional[str] = None) -> bool:
        """
        服务器添加通知

        Args:
            server_ip: 服务器IP
            added_by: 添加者
            notes: 备注
            expire_date: 过期日期
        """
        info = {
            "服务器IP": server_ip,
            "添加者": added_by,
            "添加时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "状态": "🆕 已添加到服务器池"
        }

        if notes:
            info["备注"] = notes

        if expire_date:
            info["预计过期"] = expire_date

        content = f"""
        <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
            新的服务器已添加到 Hermit Crab 服务器池中。
        </p>

        {self._create_info_table(info)}

        <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0; color: #065f46; font-size: 14px;">
                <strong>✅ 已同步：</strong>服务器信息已同步到 GitHub 和所有节点。
            </p>
        </div>
        """

        subject = f"🆕 [Hermit Crab] 新服务器已添加 - {server_ip}"
        html = self._get_base_template("服务器已添加", content, "#10b981")

        return self.send_email(subject, html)

    def notify_ssh_failed(self, server_ip: str, error_message: str, retry_count: int = 0) -> bool:
        """
        SSH 连接失败通知

        Args:
            server_ip: 服务器IP
            error_message: 错误信息
            retry_count: 重试次数
        """
        info = {
            "服务器IP": server_ip,
            "重试次数": f"{retry_count} 次",
            "失败时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "状态": "❌ SSH 连接失败"
        }

        content = f"""
        <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
            尝试连接目标服务器时失败，可能影响迁移流程。
        </p>

        {self._create_info_table(info)}

        <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0 0 8px 0; color: #991b1b; font-size: 14px; font-weight: 600;">
                ❌ 错误信息：
            </p>
            <pre style="margin: 0; color: #7f1d1d; font-size: 13px; font-family: 'Courier New', monospace; white-space: pre-wrap; word-wrap: break-word;">{error_message}</pre>
        </div>

        <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0; color: #92400e; font-size: 14px;">
                <strong>🔧 可能原因：</strong>
            </p>
            <ul style="margin: 8px 0 0 0; padding-left: 20px; color: #92400e; font-size: 14px;">
                <li>SSH 密码错误</li>
                <li>服务器防火墙阻止连接</li>
                <li>服务器 SSH 服务未启动</li>
                <li>网络连接问题</li>
            </ul>
        </div>
        """

        subject = f"❌ [Hermit Crab] SSH 连接失败 - {server_ip}"
        html = self._get_base_template("SSH 连接失败", content, "#ef4444")

        return self.send_email(subject, html)

    def notify_no_available_servers(self, current_ip: str, remaining_days: int) -> bool:
        """
        无可用服务器通知

        Args:
            current_ip: 当前服务器IP
            remaining_days: 剩余天数
        """
        info = {
            "当前服务器": current_ip,
            "剩余天数": f"{remaining_days} 天",
            "检查时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "状态": "⚠️ 无可用目标"
        }

        content = f"""
        <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
            🚨 Hermit Crab 需要执行迁移，但在服务器池中找不到合适的目标服务器。
        </p>

        {self._create_info_table(info)}

        <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0; color: #991b1b; font-size: 14px; font-weight: 600;">
                ⚠️ 紧急操作建议：
            </p>
            <ul style="margin: 8px 0 0 0; padding-left: 20px; color: #991b1b; font-size: 14px;">
                <li>立即添加新的备用服务器到服务器池</li>
                <li>检查现有服务器的状态和剩余时间</li>
                <li>考虑临时延长当前服务器的使用期限</li>
            </ul>
        </div>

        <div style="background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 16px; margin: 20px 0; border-radius: 4px;">
            <p style="margin: 0; color: #1e40af; font-size: 14px;">
                <strong>💡 添加服务器命令：</strong>
            </p>
            <pre style="margin: 8px 0 0 0; color: #1e3a8a; font-size: 13px; font-family: 'Courier New', monospace;">hermit-crab add --ip &lt;新服务器IP&gt; --notes "备用服务器"</pre>
        </div>
        """

        subject = f"🚨 [Hermit Crab] 无可用服务器 - 剩余 {remaining_days} 天"
        html = self._get_base_template("无可用服务器", content, "#ef4444")

        return self.send_email(subject, html)
