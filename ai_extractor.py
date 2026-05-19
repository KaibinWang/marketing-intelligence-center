"""AI信息抽取 - 使用DeepSeek API"""
import json
from openai import OpenAI
from config import CONFIG


# 广东地区城市（不含深圳）
GUANGDONG_CITIES = [
    "广州", "佛山", "东莞", "中山", "珠海", "江门", "肇庆", "惠州",
    "汕头", "潮州", "揭阳", "汕尾", "梅州", "河源", "韶关", "清远",
    "云浮", "阳江", "茂名", "湛江",
]


class EventExtractor:
    """使用DeepSeek从文本中抽取结构化事件信息"""

    def __init__(self, api_key=None, api_url=None, model=None):
        self.api_key = api_key or CONFIG["deepseek_api_key"]
        self.api_url = api_url or CONFIG["deepseek_api_url"]
        self.model = model or CONFIG.get("deepseek_model", "deepseek-chat")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_url,
        )

    def extract_from_cninfo(self, item):
        """从巨潮资讯网公告中提取事件信息

        Args:
            item: 公告信息dict（来自crawler_cninfo）

        Returns:
            dict: 结构化事件信息，包含 location（省份+城市）
        """
        title = item.get("title", "")
        sec_name = item.get("sec_name", "")
        sec_code = item.get("sec_code", "")

        prompt = f"""你是一个银行营销情报分析助手。请从以下上市公司公告标题中提取关键信息，以JSON格式返回。

公告标题：{title}
公司名称：{sec_name}
股票代码：{sec_code}

请提取以下字段并以JSON格式返回：
{{
    "event_type": "事件类型（中标/融资/对外投资/扩产/并购/政府补助/其他）",
    "company_name": "公司名称",
    "stock_code": "股票代码",
    "project_or_subject": "项目或事项简述（一句话）",
    "amount_estimate": "涉及金额（纯数字，单位元，如果没有就填0）",
    "pub_date": "公告日期（YYYY-MM-DD格式，如果没有就填'未知'）",
    "province": "公司注册省份（根据公司名称和公告内容判断，如广东、浙江、上海等，不确定填'未知'）",
    "city": "公司所在城市（根据公司名称和公告内容判断，如广州、深圳、杭州等，不确定填'未知'）",
    "source": "巨潮资讯网",
    "source_url": "原文链接"
}}

要求：
1. event_type 从以下选择：中标、融资、对外投资、扩产、并购、政府补助、其他
2. province 和 city 根据公司名称前缀和公告内容中的地名判断
3. amount_estimate 转换为纯数字（单位：元），没有金额就填0
4. 只返回JSON，不要其他内容"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()

        try:
            event = json.loads(content)
            event["source_url"] = item.get("detail_url", "")
            return event
        except json.JSONDecodeError:
            return {
                "event_type": "其他",
                "company_name": sec_name,
                "stock_code": sec_code,
                "project_or_subject": title,
                "amount_estimate": 0,
                "pub_date": "未知",
                "province": "未知",
                "city": "未知",
                "source": "巨潮资讯网",
                "source_url": item.get("detail_url", ""),
                "raw_text": content[:500],
            }

    def is_guangdong(self, event):
        """判断企业是否在广东（不含深圳）

        Args:
            event: 事件信息dict

        Returns:
            bool: True=广东（不含深圳），False=其他地区
        """
        province = event.get("province", "")
        city = event.get("city", "")
        company_name = event.get("company_name", "")

        # 先检查是否深圳
        if "深圳" in city or "深圳" in company_name:
            return False

        # 检查是否广东
        if province == "广东":
            return True

        # 检查城市是否在广东列表中
        if city in GUANGDONG_CITIES:
            return True

        # 公司名称包含广东城市
        for g_city in GUANGDONG_CITIES:
            if g_city in company_name:
                return True

        return False

    def extract_from_36kr(self, item):
        """从36氪融资快报中抽取结构化事件信息

        Args:
            item: 快讯信息dict（来自crawler_36kr）

        Returns:
            dict: 结构化事件信息
        """
        title = item.get("title", "")
        description = item.get("description", "")
        brief = item.get("brief", "")
        content = f"{title} {description} {brief}"

        prompt = f"""你是一个银行营销情报分析助手。请从以下36氪融资快讯中提取关键信息，以JSON格式返回。

融资快讯：{content}

请提取以下字段并以JSON格式返回：
{{
    "event_type": "事件类型（股权融资/债权融资/天使轮/A轮/B轮/C轮/Pre-IPO/IPO/战略投资/其他）",
    "company_name": "被投企业名称",
    "stock_code": "股票代码（如果没有就填'未知'）",
    "project_or_subject": "融资用途或项目简述（一句话）",
    "amount_estimate": "融资金额（纯数字，单位元，如果没有就填0）",
    "pub_date": "发布日期（YYYY-MM-DD格式）",
    "province": "公司注册省份（根据企业名称和描述判断，不确定填'未知'）",
    "city": "公司所在城市（根据企业名称和描述判断，不确定填'未知'）",
    "investor": "投资方（一句话概括）",
    "source": "36氪",
    "source_url": "原文链接"
}}

要求：
1. event_type 从融资阶段选择：天使轮、A轮、B轮、C轮、Pre-IPO、IPO、战略投资、股权融资、债权融资、其他
2. amount_estimate 转换为纯数字（单位：元），没有就填0
3. province 和 city 根据企业名称和描述中的地名判断
4. 只返回JSON，不要其他内容"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()

        try:
            event = json.loads(content)
            event["source_url"] = item.get("detail_url", "")
            return event
        except json.JSONDecodeError:
            return {
                "event_type": "其他",
                "company_name": "未知",
                "stock_code": "未知",
                "project_or_subject": title,
                "amount_estimate": 0,
                "pub_date": "未知",
                "province": "未知",
                "city": "未知",
                "source": "36氪",
                "source_url": item.get("detail_url", ""),
                "raw_text": content[:500],
            }

    def extract_from_pitchhub(self, item):
        """从 PitchHub 融资快报中抽取结构化事件信息

        PitchHub 已经提供了部分结构化字段（company / city / industry / round_name），
        但仍需 AI 从正文中提取金额、省份、投资方等。

        Args:
            item: dict（来自 PitchHubCrawler.fetch），包含：
                - title: 标题
                - description: 正文
                - company: 企业名称（可能为空）
                - city: 城市（可能为空）
                - industry: 行业（可能为空）
                - round_name: 融资轮次（可能为空）
                - detail_url: 原文链接
                - pub_time: 发布时间
                - source: 来源

        Returns:
            dict: 结构化事件信息
        """
        title = item.get("title", "")
        description = item.get("description", "")
        company = item.get("company", "") or item.get("company", "")
        city = item.get("city", "") or ""
        industry = item.get("industry", "") or ""
        round_name = item.get("round_name", "") or ""

        # 构造 prompt，把已有的结构化信息填入，降低 AI 负担
        known_prefix = ""
        if company:
            known_prefix += f"企业名称：{company}\n"
        if city:
            known_prefix += f"所在城市：{city}\n"
        if industry:
            known_prefix += f"所属行业：{industry}\n"
        if round_name:
            known_prefix += f"融资轮次：{round_name}\n"

        content = f"{title}\n{description}"

        prompt = f"""你是一个银行营销情报分析助手。请从以下融资新闻中提取关键信息，以JSON格式返回。

{known_prefix}融资快讯正文：
{content}

请提取以下字段并以JSON格式返回：
{{
    "event_type": "事件类型（股权融资/债权融资/天使轮/A轮/B轮/C轮/Pre-IPO/IPO/战略投资/其他）",
    "company_name": "被投企业名称（优先使用已知信息，如信息缺失则从正文提取）",
    "stock_code": "股票代码（如果没有就填'未知'）",
    "project_or_subject": "融资用途或项目简述（一句话）",
    "amount_estimate": "融资金额（纯数字，单位元，如果没有就填0）",
    "pub_date": "发布日期（YYYY-MM-DD格式）",
    "province": "公司注册省份（根据企业名称和描述判断，不确定填'未知'）",
    "city": "公司所在城市（优先使用已知信息，如信息缺失则从正文判断，不确定填'未知'）",
    "investor": "投资方（一句话概括，如果没有就填'未知'）",
    "source": "36氪融资快报",
    "source_url": "原文链接"
}}

要求：
1. event_type 从融资阶段选择：天使轮、A轮、B轮、C轮、Pre-IPO、IPO、战略投资、股权融资、债权融资、其他
2. amount_estimate 转换为纯数字（单位：元），没有就填0
3. province 和 city 根据企业名称和描述中的地名判断
4. 正文中有已知信息的字段（企业名称、城市、轮次等），直接使用已知信息，不要从正文重新提取
5. 只返回JSON，不要其他内容"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()

        try:
            event = json.loads(content)
            event["source_url"] = item.get("detail_url", "")
            return event
        except json.JSONDecodeError:
            return {
                "event_type": "其他",
                "company_name": company or "未知",
                "stock_code": "未知",
                "project_or_subject": title,
                "amount_estimate": 0,
                "pub_date": item.get("pub_time", "")[:10],
                "province": "未知",
                "city": city or "未知",
                "source": "36氪融资快报",
                "source_url": item.get("detail_url", ""),
                "raw_text": content[:500],
            }

    def extract_from_gdgov(self, item):
        """从广东省政府采购中心公告中提取结构化事件信息

        Args:
            item: dict（来自 GdGovCrawler），包含：
                - title: 公告标题
                - detail_text: 详情页正文
                - pub_date: 发布日期
                - detail_url: 原文链接

        Returns:
            dict: 结构化事件信息
        """
        title = item.get("title", "")
        detail_text = item.get("detail_text", "")
        pub_date = item.get("pub_date", "")

        prompt = f"""你是一个银行营销情报分析助手。请从以下政府采购中标公告中提取关键信息，以JSON格式返回。

公告标题：{title}

公告正文：
{detail_text[:3000]}

请提取以下字段并以JSON格式返回：
{{
    "event_type": "事件类型（中标/其他）",
    "company_name": "中标/成交供应商全称",
    "stock_code": "股票代码（如果没有就填'未知'）",
    "project_or_subject": "项目名称（一句话）",
    "amount_estimate": "中标金额（纯数字，单位元，如果没有就填0）",
    "purchaser": "采购人（招标人）全称",
    "pub_date": "发布日期（YYYY-MM-DD格式）",
    "province": "中标供应商注册省份（根据企业名称和公告内容判断，广东省内的填'广东'，不确定填'未知'）",
    "city": "中标供应商所在城市（根据企业名称和正文判断，如广州、佛山、东莞等，不确定填'未知'）",
    "source": "广东省政府采购中心",
    "source_url": "原文链接"
}}

要求：
1. event_type 固定为"中标"（政府采购中标公告）
2. company_name 填中标供应商名称，不是采购人
3. amount_estimate 转换为纯数字（单位：元），去除逗号和￥符号，没有就填0
4. province 和 city 根据中标供应商名称判断
5. 优先从正文中提取字段，标题作为补充
6. 只返回JSON，不要其他内容"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()

        try:
            event = json.loads(content)
            event["source_url"] = item.get("detail_url", "")
            return event
        except json.JSONDecodeError:
            return {
                "event_type": "中标",
                "company_name": "未知",
                "stock_code": "未知",
                "project_or_subject": title,
                "amount_estimate": 0,
                "purchaser": "",
                "pub_date": pub_date,
                "province": "广东",
                "city": "未知",
                "source": "广东省政府采购中心",
                "source_url": item.get("detail_url", ""),
                "raw_text": content[:500],
            }

    def generate_marketing_suggestion(self, event):
        """根据事件生成营销建议"""
        company = event.get("company_name", "未知")
        event_type = event.get("event_type", "未知")
        project = event.get("project_or_subject", "未知")
        amount = event.get("amount_estimate", 0)
        stock_code = event.get("stock_code", "")

        # 格式化金额
        if amount > 0:
            if amount >= 100000000:
                amount_str = f"{amount / 100000000:.1f}亿元"
            elif amount >= 10000:
                amount_str = f"{amount / 10000:.0f}万元"
            else:
                amount_str = f"{amount}元"
        else:
            amount_str = "未披露"

        prompt = f"""你是一个银行营销顾问。根据以下上市公司公告信息，生成营销建议。

企业信息：
- 企业名称：{company}（{stock_code}）
- 事件类型：{event_type}
- 事项：{project}
- 涉及金额：{amount_str}

请分析该企业可能的银行需求，推荐2-3个最匹配的银行产品，并说明推荐理由。
以以下格式返回：

【营销情报】
企业：{company}（{stock_code}）
事件：{event_type} - {project}
金额：{amount_str}

建议营销产品：
1. [产品名称] - [推荐理由]
2. [产品名称] - [推荐理由]
3. [产品名称] - [推荐理由]（可选）

注意：
- 推荐理由要结合公告事项特点
- 推荐产品从以下范围选择：履约保函、供应链融资、流动资金贷款、银行承兑汇票、项目融资、募集资金账户、固定资产贷款、并购贷款、跨境结算、高管财富管理、员工工资代发
- 语言简洁专业，适合客户经理阅读
- 不要编造企业的其他信息"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        return response.choices[0].message.content.strip()


if __name__ == "__main__":
    extractor = EventExtractor()

    test_items = [
        {
            "title": "广州越秀集团中标广州市地铁12号线项目",
            "sec_name": "越秀集团",
            "sec_code": "600000",
            "detail_url": "http://example.com/1",
        },
        {
            "title": "深圳华为中标深圳市5G基站建设项目",
            "sec_name": "华为",
            "sec_code": "600001",
            "detail_url": "http://example.com/2",
        },
        {
            "title": "宁波建工关于全资子公司中标宁波市东部新城项目",
            "sec_name": "宁波建工",
            "sec_code": "601789",
            "detail_url": "http://example.com/3",
        },
    ]

    for item in test_items:
        print(f"=== {item['sec_name']} ===")
        result = extractor.extract_from_cninfo(item)
        print(f"省份: {result.get('province')}, 城市: {result.get('city')}")
        print(f"广东(不含深圳): {extractor.is_guangdong(result)}")
        print()
