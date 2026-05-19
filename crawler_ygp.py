"""广东省公共资源交易平台 - 交易公告采集

数据来源：https://ygp.gdzwfw.gov.cn（广东省公共资源交易平台）
使用 Playwright 浏览器引擎绕过 API 频率限制。

数据范围涵盖：工程建设、政府采购、土地使用权、矿业权、国有产权等。
"""
import re
import json
import random
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


class YgpCrawler:
    """广东省公共资源交易平台采集器

    采集交易公告（中标/成交结果等），通过 Playwright 模拟浏览器访问。
    """

    PORTAL_URL = "https://ygp.gdzwfw.gov.cn"

    def __init__(self, proxy=None):
        self._browser = None
        self._pw = None
        self._proxy = proxy

    async def _ensure_browser(self):
        if self._browser is None:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            launch_args = {"headless": True}
            if self._proxy:
                launch_args["proxy"] = self._proxy
            self._browser = await self._pw.chromium.launch(**launch_args)

    async def close(self):
        if self._browser:
            await self._browser.close()
            await self._pw.stop()
            self._browser = None

    def _parse_amount(self, text):
        m = re.search(r'(\d+(?:\.\d+)?)\s*万', text)
        if m:
            return int(float(m.group(1)) * 10000)
        m = re.search(r'(\d+(?:\.\d+)?)\s*亿', text)
        if m:
            return int(float(m.group(1)) * 100000000)
        m = re.search(r'(\d+(?:\.\d+)?)\s*元', text)
        if m:
            return int(float(m.group(1)))
        return 0

    def _parse_date(self, text):
        m = re.search(r'(\d{4})[-/]?(\d{1,2})[-/]?(\d{1,2})', text)
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        return ""

    async def _fetch_detail_text(self, detail_url, max_wait=8):
        """打开公告详情页，提取正文文本"""
        if not detail_url:
            return ""
        try:
            detail_page = await self._browser.new_page()
            text_content = ""
            try:
                await detail_page.goto(detail_url, timeout=15000, wait_until="domcontentloaded")
                await detail_page.wait_for_timeout(max_wait * 1000)
                text_content = await detail_page.evaluate('''
                    () => {
                        // 尝试获取正文区域
                        const main = document.querySelector('.main-content, .detail-content, .notice-content, article, [class*="content"], [class*="detail"]');
                        if (main) return main.innerText.slice(0, 5000);
                        // 回退到 body
                        return document.body.innerText.slice(0, 5000);
                    }
                ''')
            except Exception as e:
                logger.warning(f"详情页加载失败: {e}")
            finally:
                await detail_page.close()
            return text_content.strip()
        except Exception as e:
            logger.warning(f"提取详情文本失败: {e}")
            return ""

    async def search_recent(self, days_back=3, max_items=20):
        """采集最近 N 天发布的交易公告

        Args:
            days_back: 搜索过去多少天
            max_items: 最多采集条数（减少以加快速度）

        Returns:
            list[dict]: 公告列表
        """
        await self._ensure_browser()
        today = date.today()
        since_date = (today - timedelta(days=days_back - 1))
        since_str = since_date.strftime("%Y%m%d") + "000000"
        today_str = today.strftime("%Y%m%d") + "235959"
        page = await self._browser.new_page()
        items = []

        try:
            ua = random.choice(USER_AGENTS)
            await page.set_extra_http_headers({"User-Agent": ua})
            await page.set_viewport_size({"width": 1920, "height": 1080})

            logger.info("正在访问门户首页...")
            await page.goto(self.PORTAL_URL, timeout=30000, wait_until="networkidle")
            await page.wait_for_timeout(3000)

            delay = random.uniform(3, 8)
            logger.info(f"随机延迟 {delay:.1f} 秒后发起搜索...")
            await page.wait_for_timeout(int(delay * 1000))

            logger.info(f"正在搜索公告（{since_date} ~ {today}）...")
            search_result = await page.evaluate(
                """([sinceStr, todayStr, maxSize]) => {
                    try {
                        return fetch('/ggzy-portal/search/v2/items', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                pageNo: 1,
                                pageSize: maxSize,
                                type: 'trading-type',
                                siteCode: '44',
                                publishStartTime: sinceStr,
                                publishEndTime: todayStr
                            })
                        }).then(r => r.json()).then(d => JSON.stringify(d));
                    } catch (e) {
                        return 'error: ' + e.message;
                    }
                }""",
                [since_str, today_str, max_items]
            )

            search_data = json.loads(search_result)
            if search_data.get("errcode") == 0:
                page_data = search_data.get("data", {}).get("pageData", [])
                logger.info(f"获取到 {len(page_data)} 条公告")

                for idx, item in enumerate(page_data):
                    title = item.get("noticeTitle", "")
                    notice_id = item.get("noticeId", "")
                    site_code = item.get("siteCode", "")
                    project_code = item.get("projectCode", "")
                    pub_date_raw = item.get("publishDate", "")
                    biz_code = item.get("bizCode")
                    pub_date = self._parse_date(pub_date_raw)

                    # 构建详情页 URL
                    detail_url = item.get("linkUrl", "")
                    if not detail_url and notice_id:
                        if biz_code:
                            detail_url = (f"{self.PORTAL_URL}/#/44/new/jygg/v3/A"
                                          f"?noticeId={notice_id}"
                                          f"&projectCode={project_code}"
                                          f"&bizCode={biz_code}"
                                          f"&siteCode={site_code}"
                                          f"&publishDate={pub_date_raw}")
                        else:
                            # 无 bizCode 时用虚拟 URL 去重
                            detail_url = f"ygp://notice/{notice_id}"

                    # 有有效链接且非虚拟的尝试抓详情页
                    detail_text = title
                    if detail_url and not detail_url.startswith("ygp://"):
                        logger.info(f"  提取详情页 ({idx+1}/{len(page_data)}): {title[:40]}...")
                        fetched = await self._fetch_detail_text(detail_url)
                        if fetched:
                            detail_text = fetched
                            logger.info(f"    成功提取 {len(fetched)} 字")
                        else:
                            logger.info(f"    无法提取详情，使用标题")
                        await page.wait_for_timeout(int(random.uniform(2, 5) * 1000))

                    items.append({
                        "title": title,
                        "detail_url": detail_url,
                        "pub_date": pub_date or today_str,
                        "source": "广东省公共资源交易平台",
                        "detail_text": detail_text,
                        "amount_estimate": 0,
                        "company_name": "",
                        "event_type": "中标",
                        "has_link": bool(detail_url and not detail_url.startswith("ygp://")),
                    })
            else:
                logger.warning(f"搜索 API 返回错误: {search_data.get('errmsg')}")

        except Exception as e:
            logger.error(f"采集失败: {e}", exc_info=True)
        finally:
            await page.close()

        return items

    async def search(self, max_pages=1):
        """兼容接口"""
        return await self.search_recent(days_back=3, max_items=20)


def search_sync(max_pages=1):
    """同步方式调用爬虫（在后台线程中执行）"""
    import asyncio

    async def _run():
        crawler = YgpCrawler()
        try:
            return await crawler.search(max_pages=max_pages)
        finally:
            await crawler.close()

    try:
        return asyncio.run(_run())
    except Exception:
        import subprocess
        try:
            subprocess.run(
                ["pkill", "-f", "chrome-headless-shell"],
                capture_output=True, timeout=3
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    items = search_sync(max_pages=1)
    print(f"\n=== 公告 ({len(items)} 条) ===")
    for i, item in enumerate(items[:10], 1):
        print(f"{i}. [{item['pub_date']}] {item['title'][:60]}")
