"""pitchhub.36kr.com 融资快报采集"""
import re
import json
import logging
import datetime

import requests

logger = logging.getLogger(__name__)


class PitchHubCrawler:
    """36氪 PitchHub 融资快报采集器

    数据来源：https://pitchhub.36kr.com/financing-flash
    页面在 __INIT_PROPS__ 中 SSR 嵌入 20 条结构化融资快报，
    每条包含标题、正文、公司名、城市、行业、融资轮次等字段。
    """

    PAGE_URL = "https://pitchhub.36kr.com/financing-flash"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def fetch(self):
        """获取融资快报列表

        Returns:
            list[dict]: 融资快报列表，每项包含：
                - title: 标题
                - description: 正文
                - source: '36氪融资快报'
                - detail_url: 详情链接
                - pub_time: 发布时间 (ISO格式)
                - company: 企业名称 (如有)
                - city: 城市 (如有)
                - industry: 行业 (如有)
                - round_name: 融资轮次 (如有)
                - investor: 投资方 (AI提取)
        """
        resp = self.session.get(self.PAGE_URL, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            logger.error(f"请求失败: {resp.status_code}")
            return []

        html = resp.text
        props = self._extract_init_props(html)
        if not props:
            logger.error("未找到 __INIT_PROPS__ 数据")
            return []

        items = props.get("itemList", [])
        results = []
        for item in items:
            tmpl = item.get("templateMaterial", {})
            title = tmpl.get("widgetTitle", "").strip()
            content = tmpl.get("widgetContent", "").strip()
            pub_ts = tmpl.get("publishTime", 0)
            item_id = item.get("itemId", "")

            if not title and not content:
                continue

            # 结构化字段 (部分条目有)
            project = item.get("projectCard", {})
            company = project.get("name", "") or ""
            city = project.get("city", {}).get("name", "") if project.get("city") else ""
            industry = ", ".join(
                t["name"] for t in project.get("tradeList", [])
            ) if project.get("tradeList") else ""
            round_name = (
                project.get("lastestFinancingRound", {}).get("name", "")
                if project.get("lastestFinancingRound") else ""
            )

            # 转换时间戳
            if pub_ts:
                pub_time = datetime.datetime.fromtimestamp(
                    pub_ts / 1000, tz=datetime.timezone(datetime.timedelta(hours=8))
                ).strftime("%Y-%m-%d %H:%M:%S")
            else:
                pub_time = ""

            # itemType=10 是文章/快讯，可直接用 36kr.com/p/{itemId}
            # itemType=20 是项目卡片，没有独立文章页
            item_type = item.get("itemType", 0)
            if item_type == 10 and item_id:
                detail_url = f"https://36kr.com/p/{item_id}"
            else:
                detail_url = ""

            results.append({
                "title": title,
                "description": content,
                "source": "36氪融资快报",
                "detail_url": detail_url,
                "pub_time": pub_time,
                "company": company,
                "city": city,
                "industry": industry,
                "round_name": round_name,
                "itemId": item_id,
            })

        logger.info(
            f"PitchHub 获取 {len(results)} 条融资快报"
        )
        return results

    @staticmethod
    def _extract_init_props(html):
        """从 HTML 中提取 __INIT_PROPS__ JSON"""
        idx = html.find("window.__INIT_PROPS__")
        if idx < 0:
            return None

        start = html.find("=", idx) + 1
        stack = 0
        end = start
        for i in range(start, len(html)):
            if html[i] == "{":
                stack += 1
            elif html[i] == "}":
                stack -= 1
                if stack == 0:
                    end = i + 1
                    break

        try:
            return json.loads(html[start:end])
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    crawler = PitchHubCrawler()
    items = crawler.fetch()
    print(f"\n共 {len(items)} 条融资快报：\n")
    for i, item in enumerate(items[:10], 1):
        print(f"{i}. {item['title']}")
        if item["company"]:
            print(f"   企业: {item['company']}  |  城市: {item['city']}  |  行业: {item['industry']}")
        print(f"   时间: {item['pub_time']}")
        print(f"   链接: {item['detail_url']}")
        print()
