#!/usr/bin/env python3
"""
营销情报中心 - 主程序

一期场景：
1. 中标情报 - 监控上市公司中标公告
2. 上市公司重大事项 - 监控融资/扩产/并购等公告

数据来源：巨潮资讯网（上市公司法定信息披露平台）
覆盖范围：广东地区（不含深圳）
"""
import sys
import time
import logging
import argparse
from datetime import datetime

from crawler_cninfo import CninfoCrawler
from crawler_36kr_pitchhub import PitchHubCrawler
from ai_extractor import EventExtractor
from notifier import WeComNotifier
from database import IntelligenceDB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# 搜索关键词配置
SEARCH_KEYWORDS = [
    {"keyword": "中标", "scene": "中标情报"},
    {"keyword": "成交", "scene": "中标情报"},
    {"keyword": "融资", "scene": "融资情报"},
    {"keyword": "对外投资", "scene": "重大事项"},
    {"keyword": "扩产", "scene": "重大事项"},
    {"keyword": "并购", "scene": "重大事项"},
    {"keyword": "政府补助", "scene": "其他"},
]


def run(max_items=5, test_mode=False):
    """执行一次完整的情报采集和推送流程

    Args:
        max_items: 每个关键词最多处理多少条
        test_mode: 测试模式（只打印不推送）
    """
    crawler = CninfoCrawler()
    crawler_pitchhub = PitchHubCrawler()
    extractor = EventExtractor()
    db = IntelligenceDB()
    notifier = WeComNotifier()

    logger.info("=== 开始采集情报 ===")
    logger.info(f"数据源: 巨潮资讯网 + 36氪融资快报(PitchHub)")
    logger.info(f"覆盖范围: 广东地区（不含深圳）")

    total_new = 0
    total_filtered_location = 0
    total_filtered_dup = 0

    # ====== 数据源1：巨潮资讯网 ======
    logger.info(f"\n{'='*50}")
    logger.info(f"数据源1：巨潮资讯网（上市公司公告）")
    logger.info(f"{'='*50}")

    for search_config in SEARCH_KEYWORDS:
        keyword = search_config["keyword"]
        scene = search_config["scene"]

        logger.info(f"\n--- 搜索关键词: {keyword} ({scene}) ---")

        try:
            items, total = crawler.search(keyword=keyword, page=1, page_size=max_items)
            logger.info(f"共找到 {total} 条，处理前 {len(items)} 条")
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            continue

        if not items:
            continue

        for idx, item in enumerate(items, 1):
            logger.info(f"  [{idx}/{len(items)}] {item['sec_name']}: {item['title'][:40]}")

            source_url = item["detail_url"]
            if db.exists(source_url):
                logger.info(f"    已存在，跳过")
                total_filtered_dup += 1
                continue

            try:
                event = extractor.extract_from_cninfo(item)
                province = event.get("province", "未知")
                city = event.get("city", "未知")
                logger.info(f"    抽取: 企业={event.get('company_name')}, {province}/{city}, 事件={event.get('event_type')}")
            except Exception as e:
                logger.error(f"    AI抽取失败: {e}")
                continue

            if not extractor.is_guangdong(event):
                logger.info(f"    非广东地区或深圳，跳过")
                total_filtered_location += 1
                continue

            try:
                suggestion = extractor.generate_marketing_suggestion(event)
            except Exception as e:
                logger.error(f"    生成营销建议失败: {e}")
                suggestion = "营销建议生成失败，请人工分析"

            detail_text = item.get("title", "")
            db.save_event(event, detail_text, suggestion, source_url)
            total_new += 1

            if not test_mode:
                logger.info(f"    推送至企业微信...")
                success = notifier.send_single_event(event, suggestion)
                if success:
                    logger.info(f"    推送成功")
                else:
                    logger.error(f"    推送失败")
            else:
                logger.info(f"    [测试模式] 跳过推送")

            time.sleep(1)

    # ====== 数据源2：PitchHub 融资快报 ======
    logger.info(f"\n{'='*50}")
    logger.info(f"数据源3：36氪融资快报(PitchHub)")
    logger.info(f"{'='*50}")

    try:
        ph_items = crawler_pitchhub.fetch()
        logger.info(f"PitchHub: 共 {len(ph_items)} 条")
    except Exception as e:
        logger.error(f"PitchHub 获取失败: {e}")
        ph_items = []

    for idx, item in enumerate(ph_items, 1):
        logger.info(f"  [{idx}/{len(ph_items)}] {item['title'][:50]}")

        source_url = item["detail_url"]
        if not source_url:
            logger.info(f"    无链接，跳过")
            continue

        if db.exists(source_url):
            logger.info(f"    已存在，跳过")
            total_filtered_dup += 1
            continue

        try:
            event = extractor.extract_from_pitchhub(item)
            province = event.get("province", "未知")
            city = event.get("city", "未知")
            logger.info(f"    抽取: 企业={event.get('company_name')}, {province}/{city}, 事件={event.get('event_type')}")
        except Exception as e:
            logger.error(f"    AI抽取失败: {e}")
            continue

        if not extractor.is_guangdong(event):
            logger.info(f"    非广东地区或深圳，跳过")
            total_filtered_location += 1
            continue

        try:
            suggestion = extractor.generate_marketing_suggestion(event)
        except Exception as e:
            logger.error(f"    生成营销建议失败: {e}")
            suggestion = "营销建议生成失败，请人工分析"

        detail_text = item["description"] or item["title"]
        db.save_event(event, detail_text, suggestion, source_url)
        total_new += 1

        if not test_mode:
            logger.info(f"    推送至企业微信...")
            success = notifier.send_single_event(event, suggestion)
            if success:
                logger.info(f"    推送成功")
            else:
                logger.error(f"    推送失败")
        else:
            logger.info(f"    [测试模式] 跳过推送")

        time.sleep(1)

    # 8. 统计
    logger.info(f"\n=== 采集完成 ===")
    logger.info(f"新增情报: {total_new} 条")
    logger.info(f"重复跳过: {total_filtered_dup} 条")
    logger.info(f"地域过滤: {total_filtered_location} 条（非广东或深圳）")

    stats = db.get_stats()
    logger.info(f"数据库统计: 总计{stats['total']}条, 新增{stats['new']}条, 已推送{stats['sent']}条")


def main():
    parser = argparse.ArgumentParser(description="营销情报中心")
    parser.add_argument("--test", action="store_true", help="测试模式（只采集不推送）")
    parser.add_argument("--max", type=int, default=5, help="每个关键词最多处理条数（默认5）")
    parser.add_argument("--keyword", type=str, help="只搜索指定关键词")
    args = parser.parse_args()

    if args.keyword:
        global SEARCH_KEYWORDS
        SEARCH_KEYWORDS = [{"keyword": args.keyword, "scene": "自定义"}]

    run(max_items=args.max, test_mode=args.test)


if __name__ == "__main__":
    main()
