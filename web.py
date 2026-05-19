#!/usr/bin/env python3
"""营销情报中心 - Web 管理端"""
import os
import math
import logging

from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard_db import DashboardDB
from config import CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title="营销情报中心 - 管理后台")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
db = DashboardDB()

PAGE_SIZE = 20


# =====================================================================
# 传统 HTML 页面路由（SPA 未覆盖的页面）
# =====================================================================

@app.get("/crawl/{crawl_id}", response_class=HTMLResponse)
async def page_crawl_detail(request: Request, crawl_id: int):
    record = db.get_crawl_detail(crawl_id)
    if not record:
        return JSONResponse({"error": "采集记录不存在"}, status_code=404)
    events = db.get_events_by_crawl(record)
    return templates.TemplateResponse("crawl_detail.html", {
        "request": request,
        "record": record,
        "events": events,
    })


# =====================================================================
# JSON API 路由
# =====================================================================

@app.get("/api/events")
async def api_list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=100),
    event_type: str = Query(""),
    company: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
    source: str = Query(""),
    status: str = Query(""),
):
    db_filters = {
        "event_type": event_type or None,
        "company": company or None,
        "date_from": date_from or None,
        "date_to": date_to or None,
        "source": source or None,
        "status": status or None,
    }
    db_filters = {k: v for k, v in db_filters.items() if v is not None}
    items, total = db.list_events(page=page, page_size=page_size, **db_filters)
    return {"items": items, "total": total, "page": page, "pages": max(math.ceil(total / page_size), 1)}


@app.get("/api/events/{event_id}")
async def api_get_event(event_id: int):
    event = db.get_event(event_id)
    if not event:
        return JSONResponse({"error": "情报不存在"}, status_code=404)
    return event


@app.get("/api/stats")
async def api_stats():
    return {
        "push_stats": db.get_push_stats(),
        "type_dist": db.get_event_type_distribution(),
        "source_dist": db.get_source_distribution(),
        "daily_trend": db.get_daily_trend(),
        "today_count": db.get_today_count(),
    }


@app.get("/api/push-logs")
async def api_push_logs(page: int = Query(1, ge=1), status: str = Query("")):
    db_filters = {"status": status} if status else {}
    logs, total = db.get_push_logs(page=page, page_size=PAGE_SIZE, **db_filters)
    return {"items": logs, "total": total, "page": page, "pages": max(math.ceil(total / PAGE_SIZE), 1)}


@app.get("/api/sources")
async def api_sources():
    return {"sources": db.get_source_status(), "history": db.get_crawl_history(page=1, page_size=20)[0]}


@app.post("/api/events/{event_id}/mark-sent")
async def api_mark_sent(event_id: int):
    from notifier import WeComNotifier
    event = db.get_event(event_id)
    if not event:
        return JSONResponse({"status": "error", "message": "情报不存在"}, status_code=404)
    settings = db.get_all_settings()
    webhook_url = settings.get("wecom_webhook_url", "")
    if not webhook_url:
        return JSONResponse({"status": "error", "message": "未配置企业微信 Webhook URL"})
    notifier = WeComNotifier(webhook_url=webhook_url)
    suggestion = event.get("marketing_suggestion", "") or ""
    try:
        ok = notifier.send_single_event(event, suggestion)
        if ok:
            db.mark_event_sent(event_id, channel="wecom")
            return {"status": "ok", "message": "发送成功"}
        else:
            return JSONResponse({"status": "error", "message": "企业微信发送失败"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"发送异常: {e}"})


@app.post("/api/run-pipeline")
async def api_run_pipeline(background_tasks: BackgroundTasks):
    """在后台执行完整采集流水线"""
    run_id = db.start_pipeline_run()
    background_tasks.add_task(_run_pipeline, run_id)
    return {"status": "ok", "run_id": run_id, "message": "已触发完整采集"}


@app.get("/api/pipeline-runs")
async def api_pipeline_runs(limit: int = Query(10, ge=1, le=50)):
    return {"items": db.get_pipeline_runs(limit=limit)}


@app.get("/api/settings")
async def api_get_settings():
    return {"settings": db.get_all_settings(), "filter_config": db.get_filter_config()}


@app.put("/api/settings")
async def api_update_settings(data: dict):
    db.update_settings(data)
    return {"status": "ok", "message": "已更新", "filter_config": db.get_filter_config()}


@app.get("/api/pipeline-latest")
async def api_pipeline_latest():
    return db.get_latest_pipeline_run() or {"status": "none"}


@app.post("/api/crawl/{source}")
async def api_trigger_crawl(source: str, request: Request, background_tasks: BackgroundTasks):
    if source not in ("cninfo", "pitchhub", "gdgov"):
        return JSONResponse({"error": "不支持的数据源"}, status_code=400)
    body = await request.json()
    keywords = body.get("keywords")
    crawl_id = db.start_crawl(source)
    background_tasks.add_task(_run_crawl, source, crawl_id, keywords)
    return {"status": "ok", "crawl_id": crawl_id, "message": f"已触发 {source} 采集任务"}


@app.get("/api/crawl-status/{crawl_id}")
async def api_crawl_status(crawl_id: int):
    status = db.get_crawl_status(crawl_id)
    if not status:
        return JSONResponse({"error": "采集记录不存在"}, status_code=404)
    # 解析 progress JSON 供前端使用
    import json
    if status.get("progress"):
        try:
            status["progress"] = json.loads(status["progress"])
        except (json.JSONDecodeError, TypeError):
            status["progress"] = []
    else:
        status["progress"] = []
    return status


@app.post("/api/crawl-cancel/{crawl_id}")
async def api_cancel_crawl(crawl_id: int):
    status = db.get_crawl_status(crawl_id)
    if not status:
        return JSONResponse({"error": "采集记录不存在"}, status_code=404)
    db.request_cancel_crawl(crawl_id)
    return {"status": "ok", "message": "已请求取消"}


@app.get("/api/health")
async def api_health():
    count = db.get_today_count()
    return {"status": "ok", "db_path": db.db_path, "today_count": count}


@app.post("/api/events/clear")
async def api_clear_events():
    db.clear_all_events()
    return {"status": "ok", "message": "已清空全部情报"}


# =====================================================================
# SPA 静态资源服务（Vue 3 + Element Plus）
# =====================================================================

FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    # 挂载编译后的 JS/CSS 静态资源
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/favicon.ico")
    async def favicon():
        fpath = os.path.join(FRONTEND_DIST, "favicon.ico")
        if os.path.isfile(fpath):
            return FileResponse(fpath)
        return JSONResponse(status_code=404, content={"error": "Not found"})

    # SPA 回退：所有非 API、非 crawl 的路由都返回 index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # 不要拦截 API 和传统页面路径
        if full_path.startswith("api/") or full_path.startswith("crawl/"):
            return JSONResponse(status_code=404, content={"error": "Not found"})
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
else:
    logger.warning("前端 dist 目录不存在（%s），SPA 不可用", FRONTEND_DIST)


# =====================================================================
# 后台完整采集流水线
# =====================================================================

def _match_filter(event, filter_config):
    """基于 settings 匹配地域过滤规则

    Args:
        event: AI 提取的事件 dict
        filter_config: get_filter_config() 返回的解析后配置

    Returns:
        True=通过，False=过滤
    """
    province = event.get("province", "") or ""
    city = event.get("city", "") or ""
    company_name = event.get("company_name", "") or ""

    enabled_provinces = filter_config.get("enabled_provinces", ["广东"])
    excluded_cities = filter_config.get("excluded_cities", ["深圳"])
    extra_cities = filter_config.get("extra_cities", [])

    # 排除城市检查
    if any(ec in city for ec in excluded_cities):
        return False
    if any(ec in company_name for ec in excluded_cities):
        return False

    # 省份白名单
    if province in enabled_provinces:
        return True

    # 额外城市（不限省份）
    if city in extra_cities:
        return True
    if any(ec in company_name for ec in extra_cities):
        return True

    return False

def _run_pipeline(run_id: int):
    """在后台执行完整采集流水线

    流程：抓取各数据源 → AI 提取 → 地域过滤 → 营销建议 → 推送
    """
    import time
    import traceback
    from ai_extractor import EventExtractor
    from notifier import WeComNotifier

    logger.info(f"=== 流水线 #{run_id} 开始 ===")
    settings = db.get_all_settings()
    extractor = EventExtractor(
        api_key=settings.get("deepseek_api_key"),
        api_url=settings.get("deepseek_api_url"),
        model=settings.get("deepseek_model"),
    )
    webhook_url = settings.get("wecom_webhook_url", "")
    notifier = WeComNotifier(webhook_url=webhook_url)
    filter_config = db.get_filter_config()

    summary = {
        "sources": {},
        "total_new": 0,
        "total_dup": 0,
        "total_filtered": 0,
        "total_pushed": 0,
        "errors": [],
    }

    def _process_items(source_name, items, detail_text_fn, extract_fn):
        """处理一批采集到的条目"""
        local_new = 0
        local_dup = 0
        local_filtered = 0
        local_pushed = 0

        for idx, item in enumerate(items):
            source_url = item.get("detail_url", "")
            if not source_url:
                item_id = item.get("itemId", "")
                source_url = f"pitchhub://item/{item_id}" if item_id else ""
            if not source_url:
                continue

            if db.exists(source_url):
                local_dup += 1
                continue

            title = item.get("title", "")
            try:
                event = extract_fn(item)
                logger.info(f"    抽取: {event.get('company_name')}, {event.get('province')}/{event.get('city')}, {event.get('event_type')}")
            except Exception as e:
                logger.error(f"    AI抽取失败: {e}")
                summary["errors"].append(f"[{source_name}] {title[:30]}: AI抽取失败 - {e}")
                continue

            if not _match_filter(event, filter_config):
                local_filtered += 1
                detail_text = detail_text_fn(item)
                db.save_event(event, detail_text, "", source_url, status="filtered")
                continue

            try:
                suggestion = extractor.generate_marketing_suggestion(event)
            except Exception as e:
                logger.error(f"    营销建议失败: {e}")
                suggestion = "营销建议生成失败，请人工分析"

            detail_text = detail_text_fn(item)
            event_id = db.save_event(event, detail_text, suggestion, source_url)
            if not event_id:
                continue
            local_new += 1

            try:
                notifier.send_single_event(event, suggestion)
                db.mark_event_sent(event_id, channel="wecom")
                local_pushed += 1
            except Exception as e:
                logger.error(f"    推送失败: {e}")

            time.sleep(1)

        return local_new, local_dup, local_filtered, local_pushed

    # ---- 数据源1: 巨潮资讯网 ----
    try:
        logger.info("采集巨潮资讯网...")
        from crawler_cninfo import CninfoCrawler
        crawler = CninfoCrawler()

        search_keywords = [
            {"keyword": "中标", "scene": "中标情报"},
            {"keyword": "成交", "scene": "中标情报"},
            {"keyword": "融资", "scene": "融资情报"},
            {"keyword": "对外投资", "scene": "重大事项"},
            {"keyword": "扩产", "scene": "重大事项"},
            {"keyword": "并购", "scene": "重大事项"},
            {"keyword": "政府补助", "scene": "其他"},
        ]

        cninfo_new = 0
        cninfo_dup = 0
        cninfo_filtered = 0
        cninfo_pushed = 0

        for sc in search_keywords:
            try:
                items, total = crawler.search(keyword=sc["keyword"], page=1, page_size=10)
                logger.info(f"  关键词 '{sc['keyword']}': 找到{total}条，处理{len(items)}条")
                n, d, f, p = _process_items(
                    "cninfo", items,
                    lambda x: x.get("title", ""),
                    lambda x: extractor.extract_from_cninfo(x),
                )
                cninfo_new += n
                cninfo_dup += d
                cninfo_filtered += f
                cninfo_pushed += p
            except Exception as e:
                logger.error(f"  关键词 '{sc['keyword']}' 失败: {e}")
                summary["errors"].append(f"[cninfo/{sc['keyword']}] {e}")

        summary["sources"]["cninfo"] = {
            "new": cninfo_new, "dup": cninfo_dup,
            "filtered": cninfo_filtered, "pushed": cninfo_pushed,
        }
        summary["total_new"] += cninfo_new
        summary["total_dup"] += cninfo_dup
        summary["total_filtered"] += cninfo_filtered
        summary["total_pushed"] += cninfo_pushed
        db.log_crawl("cninfo", "success", cninfo_new + cninfo_dup, started_at=None)
    except Exception as e:
        logger.error(f"巨潮资讯网采集失败: {e}")
        summary["errors"].append(f"[cninfo] 采集失败: {e}")
        db.log_crawl("cninfo", "failed", 0, error_msg=str(e), started_at=None)

    # ---- 数据源2: PitchHub 融资快报 ----
    try:
        logger.info("采集 PitchHub 融资快报...")
        from crawler_36kr_pitchhub import PitchHubCrawler
        crawler_ph = PitchHubCrawler()
        ph_items = crawler_ph.fetch()

        n, d, f, p = _process_items(
            "pitchhub", ph_items,
            lambda x: x.get("description", "") or x.get("title", ""),
            lambda x: extractor.extract_from_pitchhub(x),
        )
        summary["sources"]["pitchhub"] = {"new": n, "dup": d, "filtered": f, "pushed": p}
        summary["total_new"] += n
        summary["total_dup"] += d
        summary["total_filtered"] += f
        summary["total_pushed"] += p
        db.log_crawl("pitchhub", "success", len(ph_items), started_at=None)
    except Exception as e:
        logger.error(f"PitchHub采集失败: {e}")
        summary["errors"].append(f"[pitchhub] 采集失败: {e}")
        db.log_crawl("pitchhub", "failed", 0, error_msg=str(e), started_at=None)

    # ---- 数据源3: 广东省政府采购中心 ----
    try:
        logger.info("采集广东省政府采购中心...")
        from crawler_gdgov import GdGovCrawler
        crawler_gd = GdGovCrawler()
        gd_items = crawler_gd.search(max_pages=2)

        n, d, f, p = _process_items(
            "gdgov", gd_items,
            lambda x: x.get("detail_text", "") or x.get("title", ""),
            lambda x: extractor.extract_from_gdgov(x),
        )
        summary["sources"]["gdgov"] = {"new": n, "dup": d, "filtered": f, "pushed": p}
        summary["total_new"] += n
        summary["total_dup"] += d
        summary["total_filtered"] += f
        summary["total_pushed"] += p
        db.log_crawl("gdgov", "success", len(gd_items), started_at=None)
    except Exception as e:
        logger.error(f"广东省政府采购中心采集失败: {e}")
        summary["errors"].append(f"[gdgov] 采集失败: {e}")
        db.log_crawl("gdgov", "failed", 0, error_msg=str(e), started_at=None)

    db.finish_pipeline_run(run_id, "completed", summary)
    logger.info(f"=== 流水线 #{run_id} 完成: 新增{summary['total_new']}, 推送{summary['total_pushed']} ===")


# =====================================================================
# 后台爬虫任务
# =====================================================================

def _log_crawl_result(source, crawl_id, status, count, error_msg=None):
    """记录爬虫结果（兼容新旧接口）"""
    if crawl_id:
        db.finish_crawl(crawl_id, status, count, error_msg=error_msg)
    else:
        db.log_crawl(source, status, count, error_msg=error_msg)


def _run_crawl(source: str, crawl_id: int = None, keywords: list = None):
    """在后台执行单数据源采集（抓取 + AI 抽取 + 地域过滤 + 保存）"""
    import time
    from ai_extractor import EventExtractor
    extractor = EventExtractor(
        api_key=db.get_setting("deepseek_api_key"),
        api_url=db.get_setting("deepseek_api_url"),
        model=db.get_setting("deepseek_model"),
    )
    filter_config = db.get_filter_config()
    total_new = 0
    total_filtered = 0
    total_dup = 0
    errors = []

    def _check_cancel():
        if db.is_crawl_cancelled(crawl_id):
            db.update_crawl_progress(crawl_id, "⏹ 用户已取消", 0)
            _log_crawl_result(source, crawl_id, "failed", total_new+total_dup+total_filtered, error_msg="用户取消")
            logger.info(f"爬虫 {source} 已取消")
            return True
        return False

    try:
        if source == "cninfo":
            from crawler_cninfo import CninfoCrawler
            crawler = CninfoCrawler()
            search_keywords = [
                {"keyword": "中标", "scene": "中标情报"},
                {"keyword": "成交", "scene": "中标情报"},
                {"keyword": "融资", "scene": "融资情报"},
                {"keyword": "对外投资", "scene": "重大事项"},
                {"keyword": "扩产", "scene": "重大事项"},
                {"keyword": "并购", "scene": "重大事项"},
                {"keyword": "政府补助", "scene": "其他"},
            ]
            if keywords:
                search_keywords = [sk for sk in search_keywords if sk["keyword"] in keywords]
            db.update_crawl_progress(crawl_id, "正在抓取巨潮资讯网...", 5)
            all_items = []
            for sk in search_keywords:
                kw = sk["keyword"]
                try:
                    kw_items, _ = crawler.search(keyword=kw, page=1, page_size=10)
                    all_items.extend(kw_items)
                    logger.info(f"  cninfo '{kw}': {len(kw_items)} 条")
                except Exception as e:
                    logger.error(f"  cninfo '{kw}' 失败: {e}")
            if _check_cancel():
                return
            db.update_crawl_progress(crawl_id, f"共获取 {len(all_items)} 条数据，开始 AI 抽取", 10)
            total_items = len(all_items)
            for idx, item in enumerate(all_items):
                if _check_cancel():
                    return
                pct = 10 + int(80 * (idx + 1) / total_items) if total_items else 90
                source_url = item.get("detail_url", "")
                if not source_url:
                    db.update_crawl_progress(crawl_id, f"跳过第 {idx+1} 条（无链接）", pct)
                    continue
                if db.exists(source_url):
                    total_dup += 1
                    db.update_crawl_progress(crawl_id, f"跳过第 {idx+1}/{total_items} 条（重复）", pct)
                    continue
                try:
                    event = extractor.extract_from_cninfo(item)
                except Exception as e:
                    errors.append(f"AI抽取失败: {e}")
                    db.update_crawl_progress(crawl_id, f"第 {idx+1}/{total_items} 条 AI 抽取失败", pct)
                    continue
                db.update_crawl_progress(crawl_id, f"正在处理: {event.get('company_name','?')} ({event.get('province','?')}/{event.get('city','?')})", pct)
                if not _match_filter(event, filter_config):
                    total_filtered += 1
                    db.save_event(event, item.get("title", ""), "", source_url, status="filtered")
                    continue
                try:
                    suggestion = extractor.generate_marketing_suggestion(event)
                except Exception:
                    suggestion = ""
                db.save_event(event, item.get("title", ""), suggestion, source_url)
                total_new += 1
                time.sleep(0.5)

        elif source == "pitchhub":
            from crawler_36kr_pitchhub import PitchHubCrawler
            crawler = PitchHubCrawler()
            db.update_crawl_progress(crawl_id, "正在抓取 PitchHub 融资快报...", 5)
            items = crawler.fetch()
            if _check_cancel():
                return
            db.update_crawl_progress(crawl_id, f"共获取 {len(items)} 条数据，开始 AI 抽取", 10)
            for idx, item in enumerate(items):
                if _check_cancel():
                    return
                source_url = item.get("detail_url", "")
                if not source_url:
                    # 项目卡片没有独立文章页，用虚拟 URL 去重
                    item_id = item.get("itemId", "") or str(hash(str(item)))
                    source_url = f"pitchhub://item/{item_id}"
                    item["detail_url"] = source_url
                    db.update_crawl_progress(crawl_id, f"第 {idx+1} 条无独立链接，使用虚拟 ID", 10 + int(80 * (idx+1) / len(items)))
                if db.exists(source_url):
                    total_dup += 1
                    db.update_crawl_progress(crawl_id, f"跳过第 {idx+1}/{len(items)} 条（重复）", 10 + int(80 * (idx+1) / len(items)))
                    continue
                try:
                    event = extractor.extract_from_pitchhub(item)
                except Exception as e:
                    errors.append(f"AI抽取失败: {e}")
                    db.update_crawl_progress(crawl_id, f"第 {idx+1}/{len(items)} 条 AI 抽取失败", 10 + int(80 * (idx+1) / len(items)))
                    continue
                db.update_crawl_progress(crawl_id, f"正在处理: {event.get('company_name','?')} ({event.get('province','?')}/{event.get('city','?')})", 10 + int(80 * (idx+1) / len(items)))
                if not _match_filter(event, filter_config):
                    total_filtered += 1
                    db.save_event(event, item.get("description", ""), "", source_url, status="filtered")
                    continue
                try:
                    suggestion = extractor.generate_marketing_suggestion(event)
                except Exception:
                    suggestion = ""
                db.save_event(event, item.get("description", ""), suggestion, source_url)
                total_new += 1
                time.sleep(0.5)

        elif source == "gdgov":
            from crawler_gdgov import GdGovCrawler
            crawler = GdGovCrawler()
            db.update_crawl_progress(crawl_id, "正在抓取广东省政府采购中心...", 10)
            items = crawler.search(max_pages=2)
            if _check_cancel():
                return
            db.update_crawl_progress(crawl_id, f"共获取 {len(items)} 条公告，开始 AI 抽取", 15)
            for idx, item in enumerate(items):
                if _check_cancel():
                    return
                source_url = item.get("detail_url", "")
                if not source_url:
                    continue
                if db.exists(source_url):
                    total_dup += 1
                    continue
                pct = 15 + int(80 * (idx + 1) / len(items))
                try:
                    event = extractor.extract_from_gdgov(item)
                except Exception as e:
                    errors.append(f"AI抽取失败: {e}")
                    db.update_crawl_progress(crawl_id, f"第 {idx+1}/{len(items)} 条 AI 抽取失败", pct)
                    continue
                db.update_crawl_progress(crawl_id, f"正在处理: {event.get('company_name','?')} ({event.get('province','?')}/{event.get('city','?')})", pct)
                if not _match_filter(event, filter_config):
                    total_filtered += 1
                    db.save_event(event, item.get("detail_text", ""), "", source_url, status="filtered")
                    continue
                try:
                    suggestion = extractor.generate_marketing_suggestion(event)
                except Exception:
                    suggestion = ""
                db.save_event(event, item.get("detail_text", ""), suggestion, source_url)
                total_new += 1
                time.sleep(0.5)

        total_fetched = total_new + total_dup + total_filtered
        summary_msg = f"完成: 新增 {total_new} 条, 过滤 {total_filtered} 条, 重复 {total_dup} 条"
        db.update_crawl_progress(crawl_id, summary_msg, 100)
        _log_crawl_result(source, crawl_id, "success", total_fetched)
        logger.info(f"爬虫 {source} 完成: {summary_msg}")
    except Exception as e:
        logger.error(f"爬虫 {source} 失败: {e}")
        db.update_crawl_progress(crawl_id, f"❌ 失败: {e}", 0)
        _log_crawl_result(source, crawl_id, "failed", 0, error_msg=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web:app", host="0.0.0.0", port=8000, reload=True)
