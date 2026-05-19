"""巨潮资讯网 API - 上市公司公告采集"""
import time
import requests


class CninfoCrawler:
    """巨潮资讯网公告采集器"""

    API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "http://www.cninfo.com.cn/",
            "Content-Type": "application/x-www-form-urlencoded",
        })

    def search(self, keyword="", category="", page=1, page_size=20):
        """搜索公告

        Args:
            keyword: 搜索关键词（如"中标"、"融资"、"对外投资"）
            category: 公告类别（留空则搜索全部）
            page: 页码
            page_size: 每页条数

        Returns:
            list: 公告列表
        """
        data = {
            "pageNum": str(page),
            "pageSize": str(page_size),
            "column": "szse",       # szse=深交所，sse=上交所，bj=北交所
            "tabName": "fulltext",
            "plate": "",
            "stock": "",
            "searchkey": keyword,
            "secid": "",
            "category": category,
            "trade": "",
            "seDate": "",           # 日期范围，如"2026-05-01~2026-05-15"
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }

        resp = self.session.post(self.API_URL, data=data, timeout=15)
        resp.encoding = "utf-8"

        if resp.status_code != 200:
            print(f"API请求失败: {resp.status_code}")
            return [], 0

        result = resp.json()
        announcements = result.get("announcements", [])
        total = result.get("totalRecordNum", 0)

        items = []
        for ann in announcements:
            # 清理HTML标签
            title = ann.get("announcementTitle", "")
            title = title.replace("<em>", "").replace("</em>", "")

            items.append({
                "title": title,
                "sec_name": ann.get("secName", ""),      # 公司名称
                "sec_code": ann.get("secCode", ""),      # 股票代码
                "announcement_id": ann.get("announcementId", ""),
                "adjunct_url": ann.get("adjunctUrl", ""), # PDF相对路径
                "announcement_time": ann.get("announcementTime", ""),  # 公告时间（时间戳）
                "category_name": ann.get("categoryName", ""),  # 类别
                "detail_url": f"https://static.cninfo.com.cn/{ann.get('adjunctUrl', '')}" if ann.get('adjunctUrl') else f"http://www.cninfo.com.cn/new/announcementDetail?announcementId={ann.get('announcementId')}",
            })

        return items, total

    def fetch_detail_text(self, announcement_id):
        """获取公告详情文本（通过巨潮的文本接口）

        Args:
            announcement_id: 公告ID

        Returns:
            str: 公告文本内容
        """
        url = f"http://www.cninfo.com.cn/new/announcementDetail?announcementId={announcement_id}"
        resp = self.session.get(url, timeout=15)
        resp.encoding = "utf-8"

        # 从HTML中提取文本
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")

        # 尝试提取主要内容
        content = soup.select_one("div.content, div.announcement-content, #content")
        if content:
            for tag in content(["script", "style"]):
                tag.decompose()
            return content.get_text(separator="\n", strip=True)

        return soup.get_text(separator="\n", strip=True)


if __name__ == "__main__":
    crawler = CninfoCrawler()

    print("=== 测试：搜索中标公告 ===\n")
    items, total = crawler.search(keyword="中标", page=1, page_size=5)
    print(f"共找到 {total} 条，显示前 {len(items)} 条:\n")

    for i, item in enumerate(items, 1):
        print(f"{i}. [{item['sec_code']}] {item['sec_name']}")
        print(f"   {item['title']}")
        print(f"   时间: {item['announcement_time']}")
        print(f"   链接: {item['detail_url']}")
        print()

    print("=== 测试：搜索融资公告 ===\n")
    items2, total2 = crawler.search(keyword="融资", page=1, page_size=3)
    print(f"共找到 {total2} 条，显示前 {len(items2)} 条:\n")

    for i, item in enumerate(items2, 1):
        print(f"{i}. [{item['sec_code']}] {item['sec_name']}")
        print(f"   {item['title']}")
        print()
