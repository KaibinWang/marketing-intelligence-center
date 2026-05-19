"""企业微信消息推送"""
import requests
import logging
from config import CONFIG

logger = logging.getLogger(__name__)


class WeComNotifier:
    """企业微信群机器人消息推送"""

    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url or CONFIG.get("wecom_webhook_url", "")

    def send_markdown(self, content):
        """发送Markdown格式消息

        Args:
            content: Markdown文本内容

        Returns:
            bool: 发送是否成功
        """
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }

        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            result = resp.json()
            if result.get("errcode") == 0:
                logger.info("企业微信消息发送成功")
                return True
            else:
                logger.error(f"企业微信消息发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"企业微信消息发送异常: {e}")
            return False

    def send_single_event(self, event, marketing_suggestion):
        """发送单条情报到企业微信

        Args:
            event: 事件信息（dict）
            marketing_suggestion: AI生成的营销建议（str）
        """
        company = event.get("company_name", "未知")
        stock_code = event.get("stock_code", "")
        event_type = event.get("event_type", "未知")
        project = event.get("project_or_subject", "未知")
        amount = event.get("amount_estimate", 0)
        province = event.get("province", "")
        city = event.get("city", "")

        if amount > 0:
            if amount >= 100000000:
                amount_str = f"{amount / 100000000:.1f}亿元"
            elif amount >= 10000:
                amount_str = f"{amount / 10000:.0f}万元"
            else:
                amount_str = f"{amount}元"
        else:
            amount_str = "未披露"

        stock_info = f"（{stock_code}）" if stock_code else ""
        location = f"{province}{city}" if province and city and province != "未知" else ""

        content = f"""<font color="info">【{event_type}情报】</font>

**企业**：{company}{stock_info}
**地区**：{location}
**事项**：{project}
**金额**：{amount_str}

{marketing_suggestion}

<font color="comment">来源：{event.get("source", "巨潮资讯网")} | 覆盖范围：广东（不含深圳）</font>"""

        return self.send_markdown(content)

    def send_daily_summary(self, events):
        """发送每日情报汇总

        Args:
            events: 事件列表
        """
        if not events:
            return

        lines = [f"<font color=\"info\">【每日情报汇总】</font>\n共发现 **{len(events)}** 条情报\n"]

        for i, event in enumerate(events, 1):
            company = event.get("company_name", "未知")
            event_type = event.get("event_type", "未知")
            project = event.get("project_or_subject", "未知")
            amount = event.get("amount_estimate", 0)
            city = event.get("city", "")

            if amount > 0:
                if amount >= 100000000:
                    amount_str = f"{amount / 100000000:.1f}亿"
                elif amount >= 10000:
                    amount_str = f"{amount / 10000:.0f}万"
                else:
                    amount_str = str(amount)
            else:
                amount_str = "未披露"

            location = f" | {city}" if city and city != "未知" else ""
            lines.append(f"**{i}. [{event_type}] {company}{location}** — {project[:30]}（{amount_str}）")

        content = "\n".join(lines)
        return self.send_markdown(content)


if __name__ == "__main__":
    # 测试推送
    logging.basicConfig(level=logging.INFO)
    notifier = WeComNotifier()

    test_event = {
        "company_name": "越秀集团",
        "stock_code": "600000",
        "event_type": "中标",
        "project_or_subject": "中标广州市地铁12号线项目",
        "amount_estimate": 85000000,
        "province": "广东",
        "city": "广州",
    }
    test_suggestion = "建议营销产品：\n1. 履约保函 - 中标项目通常需提供履约担保\n2. 供应链融资 - 项目涉及上下游采购\n3. 流动资金贷款 - 项目前期垫资需求大"

    notifier.send_single_event(test_event, test_suggestion)
