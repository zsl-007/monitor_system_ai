# modules/webhook.py
"""
Webhook 推送模块
负责报警信息的 Webhook 推送和推送记录管理
"""

import json
import hmac
import hashlib
import time
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional

from modules.database import (
    execute_query, execute_single, execute_insert, execute_update
)
from modules.logger import logger


class WebhookManager:
    def __init__(self):
        self.webhooks: List[Dict[str, Any]] = []
        self._load_webhooks()

    def _load_webhooks(self):
        """加载所有启用的 Webhook 配置（表不存在时静默跳过）"""
        try:
            # 先探测表是否存在：sqlite_master 表永远存在，查询本身不会失败，
            # 这样就能避免触碰 webhook_config 时被 database 层打 ERROR 日志
            check = execute_single(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='webhook_config'"
            )
            if not check:
                self.webhooks = []
                logger.debug("webhook_config 表尚未创建，跳过加载")
                return

            rows = execute_query(
                'SELECT * FROM webhook_config WHERE enabled = 1 ORDER BY id'
            )
            self.webhooks = [dict(r) for r in rows]
            logger.info(f"加载了 {len(self.webhooks)} 个启用的 Webhook 配置")
        except Exception as e:
            # 兜底：即使出了别的岔子也不让初始化崩掉
            self.webhooks = []
            logger.debug(f"暂时无法加载 Webhook 配置: {e}")

    # ------- 配置 CRUD -------
    def get_all_webhooks(self) -> List[Dict[str, Any]]:
        rows = execute_query('SELECT * FROM webhook_config ORDER BY id')
        return [dict(r) for r in rows]

    def create_webhook(self, data: Dict[str, Any]) -> Optional[int]:
        try:
            wid = execute_insert(
                '''INSERT INTO webhook_config (name, url, secret, enabled)
                   VALUES (?, ?, ?, ?)''',
                (data['name'], data['url'],
                 data.get('secret', ''), data.get('enabled', True))
            )
            self._load_webhooks()
            return wid
        except Exception as e:
            logger.error(f"创建 Webhook 配置失败: {e}")
            return None

    def update_webhook(self, webhook_id: int, data: Dict[str, Any]) -> bool:
        try:
            fields, values = [], []
            for f in ['name', 'url', 'secret', 'enabled']:
                if f in data:
                    fields.append(f"{f} = ?")
                    values.append(data[f])
            if not fields:
                return False
            fields.append("updated_time = ?")
            values.append(datetime.now().isoformat())
            values.append(webhook_id)
            success = execute_update(
                f"UPDATE webhook_config SET {', '.join(fields)} WHERE id = ?",
                tuple(values)
            )
            if success:
                self._load_webhooks()
            return success
        except Exception as e:
            logger.error(f"更新 Webhook 配置失败: {e}")
            return False

    def delete_webhook(self, webhook_id: int) -> bool:
        try:
            execute_update(
                'DELETE FROM webhook_push_records WHERE webhook_id = ?',
                (webhook_id,)
            )
            success = execute_update(
                'DELETE FROM webhook_config WHERE id = ?', (webhook_id,)
            )
            if success:
                self._load_webhooks()
            return success
        except Exception as e:
            logger.error(f"删除 Webhook 配置失败: {e}")
            return False

    @staticmethod
    def _detect_platform(url: str) -> str:
        """根据 URL 识别消息平台"""
        url_lower = url.lower()
        if 'qyapi.weixin.qq.com' in url_lower:
            return 'wecom'
        elif 'oapi.dingtalk.com' in url_lower:
            return 'dingtalk'
        elif 'open.feishu.cn' in url_lower:
            return 'feishu'
        return 'generic'

    @staticmethod
    def build_signed_request(payload: Dict[str, Any], secret: str = ""):
        """
        构建签名后的请求体与请求头。
        返回 (body_bytes, headers)，调用方用 client.post(url, content=body_bytes, headers=headers) 发送。
        
        关键点：签名和发送使用完全相同的字节流，避免 json= 与 json.dumps 序列化参数不一致。
        """
        body_bytes = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if secret:
            timestamp = str(int(time.time()))
            signed_content = timestamp.encode("utf-8") + b"." + body_bytes
            signature = hmac.new(
                secret.encode("utf-8"), signed_content, hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature-V2"] = signature
            headers["X-Webhook-Timestamp"] = timestamp
        return body_bytes, headers

    def _build_platform_payload(self, platform: str, alert_record,
                                project_name: str) -> Dict[str, Any]:
        """按平台构建对应的消息体"""
        monitor_type = getattr(alert_record, 'monitor_type', '')
        alert_message = getattr(alert_record, 'alert_message', '')
        alert_time = getattr(alert_record, 'alert_time', None)

        if alert_time:
            text_content = (
                f"🚨 报警通知\n"
                f"项目：{project_name}\n"
                f"类型：{monitor_type}\n"
                f"信息：{alert_message}\n"
                f"时间：{alert_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            text_content = (
                f"🚨 报警通知\n"
                f"项目：{project_name}\n"
                f"类型：{monitor_type}\n"
                f"信息：{alert_message}"
            )

        if platform == 'wecom':
            # 企业微信群机器人：{"msgtype":"text","text":{"content":"..."}}
            return {
                "msgtype": "text",
                "text": {"content": text_content}
            }

        if platform == 'dingtalk':
            # 钉钉群机器人
            return {
                "msgtype": "text",
                "text": {"content": text_content}
            }

        if platform == 'feishu':
            # 飞书群机器人
            return {
                "msg_type": "text",
                "content": {"text": text_content}
            }

        # 通用格式（保留原有结构）
        return {
            "event_type": "monitor_alert",
            "project_name": project_name,
            "alert": {
                "config_id": getattr(alert_record, 'config_id', None),
                "monitor_type": getattr(alert_record, 'monitor_type', ''),
                "alert_message": getattr(alert_record, 'alert_message', ''),
                "alert_time": (
                    alert_record.alert_time.strftime('%Y-%m-%d %H:%M:%S')
                    if getattr(alert_record, 'alert_time', None) else ''
                ),
            }
        }

    # ------- 推送 -------
    async def push_alert(self, alert_id: int, alert_record) -> List[Dict[str, Any]]:
        results = []
        if not self.webhooks:
            logger.debug("没有启用的 Webhook，跳过推送")
            return results

        # 从系统配置中读取真实项目名称（而不是硬编码）
        try:
            from modules.config import ConfigManager
            project_name = ConfigManager().get_project_name()
        except Exception:
            project_name = "系统监测平台"

        async with httpx.AsyncClient(timeout=10.0) as client:
            for wh in self.webhooks:
                # 按每个 webhook 的 URL 识别平台，构建对应格式的 payload
                platform = self._detect_platform(wh['url'])
                payload = self._build_platform_payload(
                    platform, alert_record, project_name
                )
                results.append(
                    await self._push_single(client, wh, payload, alert_id, platform)
                )
        return results

    async def _push_single(self, client, webhook, payload, alert_id, platform='generic'):
        result = {
            "webhook_id": webhook['id'],
            "webhook_name": webhook['name'],
            "webhook_url": webhook['url'],
            "success": False, "response_code": 0, "error_message": ""
        }
        try:
            """
            headers = {"Content-Type": "application/json"}
            if webhook.get('secret'):
                timestamp = str(int(time.time()))
                signed = f"{timestamp}.{json.dumps(payload, ensure_ascii=False)}"
                signature = hmac.new(
                    webhook['secret'].encode(), signed.encode(), hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature-V2"] = signature
                headers["X-Webhook-Timestamp"] = timestamp

            resp = await client.post(webhook['url'], json=payload, headers=headers)
            result["response_code"] = resp.status_code
            """
            # 关键修复：手动序列化 body，让签名计算和实际发送使用完全相同的字节流。
            # httpx 的 json= 参数内部使用 ensure_ascii=False, separators=(",", ":")，
            # 我们手工用相同参数序列化，再通过 content= 发送，确保 body 完全一致。
            body_bytes, headers = self.build_signed_request(
                payload, webhook.get('secret', '')
            )
            if webhook.get('secret'):
                logger.debug(
                    f"[Webhook签名] {webhook['name']} "
                    f"timestamp={headers.get('X-Webhook-Timestamp')} "
                    f"body_len={len(body_bytes)} "
                    f"signature={headers.get('X-Webhook-Signature-V2', '')[:16]}..."
                )

            resp = await client.post(
                webhook['url'], content=body_bytes, headers=headers
            )
            result["response_code"] = resp.status_code

            if not (200 <= resp.status_code < 300):
                result["error_message"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(f"Webhook 推送失败: {webhook['name']} -> {result['error_message']}")
            else:
                # HTTP 200 不代表业务成功，需要看响应体里的 errcode
                business_ok = True
                err_msg = ""
                if platform in ('wecom', 'dingtalk', 'feishu'):
                    try:
                        resp_json = resp.json()
                    except Exception:
                        resp_json = {}

                    if platform == 'wecom':
                        errcode = resp_json.get('errcode', 0)
                        if errcode != 0:
                            business_ok = False
                            err_msg = (
                                f"errcode={errcode}: "
                                f"{resp_json.get('errmsg', '未知错误')}"
                            )
                    elif platform == 'dingtalk':
                        errcode = resp_json.get('errcode', 0)
                        if errcode != 0:
                            business_ok = False
                            err_msg = (
                                f"errcode={errcode}: "
                                f"{resp_json.get('errmsg', '未知错误')}"
                            )
                    elif platform == 'feishu':
                        code = resp_json.get('code', 0)
                        if code != 0:
                            business_ok = False
                            err_msg = (
                                f"code={code}: "
                                f"{resp_json.get('msg', '未知错误')}"
                            )

                if business_ok:
                    result["success"] = True
                    logger.info(f"Webhook 推送成功: {webhook['name']}")
                else:
                    result["success"] = False
                    result["error_message"] = err_msg
                    logger.warning(
                        f"Webhook 业务失败: {webhook['name']} -> {err_msg}"
                    )                
        except Exception as e:
            result["error_message"] = str(e)[:500]
            logger.error(f"Webhook 推送异常: {webhook['name']} -> {e}")

        try:
            execute_insert(
                '''INSERT INTO webhook_push_records
                   (alert_id, webhook_id, webhook_name, webhook_url,
                    success, response_code, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (alert_id, webhook['id'], webhook['name'], webhook['url'],
                 result['success'], result['response_code'], result['error_message'])
            )
        except Exception as e:
            logger.error(f"写入 Webhook 推送记录失败: {e}")

        return result

    # ------- 查询 -------
    def get_push_records_by_alert(self, alert_id: int) -> List[Dict[str, Any]]:
        rows = execute_query(
            'SELECT * FROM webhook_push_records WHERE alert_id = ? ORDER BY pushed_time',
            (alert_id,)
        )
        return [dict(r) for r in rows]

    def get_push_records_for_alerts(self, alert_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        """批量查询多条报警的 Webhook 推送记录（避免 N+1 查询）"""
        if not alert_ids:
            return {}
        placeholders = ','.join('?' for _ in alert_ids)
        rows = execute_query(
            f'''SELECT * FROM webhook_push_records
                WHERE alert_id IN ({placeholders})
                ORDER BY pushed_time''',
            tuple(alert_ids)
        )
        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for r in rows:
            d = dict(r)
            grouped.setdefault(d['alert_id'], []).append(d)
        return grouped