"""广东省政府采购中心 - 中标结果公告采集"""
import re
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class GdGovCrawler:
    """广东省政府采购中心 中标/成交结果公告采集器

    数据来源：http://gpcgd.gd.gov.cn/bsfw/cgxx/fzc/zbjjgs/
    """

    LIST_URL = "http://gpcgd.gd.gov.cn/bsfw/cgxx/fzc/zbjjgs"
    BASE_URL = "http://gpcgd.gd.gov.cn"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def fetch_list(self, page=1):
        """获取中标结果公告列表

        Args:
            page: 页码（从1开始）

        Returns:
            list[dict]: 公告列表，每项包含 title, detail_url
        """
        if page == 1:
            url = f"{self.LIST_URL}/"
        else:
            url = f"{self.LIST_URL}/index_{page}.html"

        resp = self.session.get(url, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            logger.error(f"列表页请求失败: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []
        seen_urls = set()

        for a in soup.find_all("a", href=re.compile(r"content/post_\d+\.html")):
            href = a.get("href", "").strip()
            title = a.get_text(strip=True)
            if not title or not href:
                continue

            if href.startswith("http"):
                full_url = href
            else:
                full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else f"{self.BASE_URL}/{href}"

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            items.append({
                "title": title,
                "detail_url": full_url,
            })

        logger.info(f"gpcgd 第{page}页: {len(items)} 条")
        return items

    def fetch_detail(self, url):
        """获取公告详情文本

        Args:
            url: 详情页URL

        Returns:
            str: 纯文本正文
        """
        resp = self.session.get(url, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, "lxml")
        body = soup.find("body")
        return body.get_text(separator="\n", strip=True) if body else resp.text

    def _parse_pub_date(self, text):
        """从正文中提取发布日期"""
        m = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", text)
        return m.group(1).replace("/", "-") if m else ""

    def search(self, keyword="", max_pages=3):
        """搜索广东省政府采购中标公告

        Args:
            keyword: 搜索关键词（如"中标"），留空获取所有
            max_pages: 最大翻页数

        Returns:
            list[dict]: 每项包含 title, detail_url, detail_text, pub_date, source
        """
        all_items = []

        for page in range(1, max_pages + 1):
            items = self.fetch_list(page=page)
            if not items:
                break

            if keyword:
                items = [it for it in items if keyword in it["title"]]

            for item in items:
                try:
                    detail_text = self.fetch_detail(item["detail_url"])
                    item["detail_text"] = detail_text
                    item["pub_date"] = self._parse_pub_date(detail_text)
                    item["source"] = "广东省政府采购中心"
                except Exception as e:
                    logger.error(f"详情失败 {item['detail_url']}: {e}")

            all_items.extend(items)

        logger.info(f"gpcgd: 关键词='{keyword}', 共 {len(all_items)} 条")
        return all_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    crawler = GdGovCrawler()

    print("=== 最新中标公告 ===\n")
    items = crawler.search(max_pages=1)
    for i, item in enumerate(items[:5], 1):
        print(f"{i}. {item['title']}")
        print(f"   日期: {item.get('pub_date', '')}")
        print(f"   链接: {item.get('detail_url', '')}")
        print(f"   正文长度: {len(item.get('detail_text', ''))} 字符")
        print()
