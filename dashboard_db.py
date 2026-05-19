"""仪表盘数据库扩展 - 继承 IntelligenceDB 增加仪表盘查询方法"""
import sqlite3
import time
from database import IntelligenceDB


class DashboardDB(IntelligenceDB):
    """仪表盘数据库，继承 IntelligenceDB 的所有方法，增加查询/统计/推送日志功能"""

    def __init__(self, db_path=None):
        if db_path is None:
            from config import CONFIG
            db_path = CONFIG.get("db_path", "./data/intelligence.db")
        super().__init__(db_path)
        self._ensure_dashboard_tables()

    def _ensure_dashboard_tables(self):
        """创建仪表盘新增表（幂等，不影响已有数据）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS push_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL REFERENCES events(id),
                    channel TEXT DEFAULT 'wecom',
                    push_time TEXT DEFAULT (datetime('now')),
                    status TEXT NOT NULL,
                    error_msg TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crawl_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    items_fetched INTEGER DEFAULT 0,
                    error_msg TEXT,
                    started_at TEXT DEFAULT (datetime('now')),
                    finished_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_push_event ON push_logs(event_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_push_status ON push_logs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_source ON crawl_history(source)")
            # 迁移：crawl_history 新增列（幂等）
            for col, col_type in [("progress", "TEXT"), ("cancel_requested", "INTEGER DEFAULT 0")]:
                try:
                    conn.execute(f"ALTER TABLE crawl_history ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass  # 列已存在
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL DEFAULT 'running',
                    started_at TEXT DEFAULT (datetime('now')),
                    finished_at TEXT,
                    summary TEXT,
                    error_msg TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON events(created_at)")
            # 初始化默认设置
            self._init_default_settings(conn)
            conn.commit()

    # ====== 情报列表查询 ======

    def list_events(self, page=1, page_size=20, event_type=None, company=None,
                    date_from=None, date_to=None, source=None, status=None):
        """分页查询情报列表，支持多维度筛选"""
        conditions = []
        params = []

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if company:
            conditions.append("company_name LIKE ?")
            params.append(f"%{company}%")
        if date_from:
            conditions.append("date(created_at) >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("date(created_at) <= ?")
            params.append(date_to)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM events {where}", params
            )
            total = cursor.fetchone()[0]

            offset = (page - 1) * page_size
            cursor = conn.execute(
                f"SELECT * FROM events {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [page_size, offset]
            )
            items = [dict(row) for row in cursor.fetchall()]

        return items, total

    def get_event(self, event_id):
        """查询单条情报详情"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ====== 统计分析 ======

    def get_event_type_distribution(self):
        """按事件类型分组统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT event_type, COUNT(*) as cnt FROM events GROUP BY event_type ORDER BY cnt DESC"
            )
            return [{"event_type": row[0], "count": row[1]} for row in cursor.fetchall()]

    def get_source_distribution(self):
        """按数据源分组统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM events GROUP BY source ORDER BY cnt DESC"
            )
            return [{"source": row[0], "count": row[1]} for row in cursor.fetchall()]

    def get_push_stats(self):
        """推送统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) as pushed,
                    SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) as not_pushed
                FROM events
            """)
            row = cursor.fetchone()
            total = row[0] or 0
            pushed = row[1] or 0
            not_pushed = row[2] or 0
            rate = round(pushed / total * 100, 1) if total > 0 else 0
            return {"total": total, "pushed": pushed, "not_pushed": not_pushed, "rate": rate}

    def get_daily_trend(self, days=30):
        """近 N 天每日新增趋势"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT date(created_at) as day, COUNT(*) as cnt
                FROM events
                WHERE date(created_at) >= date('now', '-{} days')
                GROUP BY date(created_at)
                ORDER BY day ASC
            """.format(days))
            return [{"day": row[0], "count": row[1]} for row in cursor.fetchall()]

    def get_amount_distribution(self):
        """按金额区间统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    SUM(CASE WHEN amount_estimate > 0 AND amount_estimate < 100000 THEN 1 ELSE 0 END) as range_lt_10w,
                    SUM(CASE WHEN amount_estimate >= 100000 AND amount_estimate < 1000000 THEN 1 ELSE 0 END) as range_10w_100w,
                    SUM(CASE WHEN amount_estimate >= 1000000 AND amount_estimate < 10000000 THEN 1 ELSE 0 END) as range_100w_1000w,
                    SUM(CASE WHEN amount_estimate >= 10000000 THEN 1 ELSE 0 END) as range_gt_1000w,
                    SUM(CASE WHEN amount_estimate IS NULL OR amount_estimate = 0 THEN 1 ELSE 0 END) as range_unknown
                FROM events
            """)
            row = cursor.fetchone()
            return [
                {"label": "10万以下", "count": row[0] or 0},
                {"label": "10万~100万", "count": row[1] or 0},
                {"label": "100万~1000万", "count": row[2] or 0},
                {"label": "1000万以上", "count": row[3] or 0},
                {"label": "未知金额", "count": row[4] or 0},
            ]

    def get_top_companies(self, limit=10):
        """企业排行"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT company_name, COUNT(*) as cnt
                FROM events
                WHERE company_name IS NOT NULL AND company_name != '' AND company_name != '未知'
                GROUP BY company_name
                ORDER BY cnt DESC
                LIMIT ?
            """, (limit,))
            return [{"company_name": row[0], "count": row[1]} for row in cursor.fetchall()]

    def get_status_distribution(self):
        """按状态统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT status, COUNT(*) as cnt
                FROM events
                GROUP BY status
                ORDER BY cnt DESC
            """)
            return [{"status": row[0], "count": row[1]} for row in cursor.fetchall()]

    # ====== 推送日志 ======

    def log_push(self, event_id, channel="wecom", status="success", error_msg=None):
        """记录一次推送"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO push_logs (event_id, channel, status, error_msg) VALUES (?, ?, ?, ?)",
                (event_id, channel, status, error_msg)
            )
            conn.commit()

    def get_push_logs(self, page=1, page_size=20, status=None):
        """分页查询推送记录（JOIN events 表获取企业名称）"""
        conditions = []
        params = []
        if status:
            conditions.append("pl.status = ?")
            params.append(status)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM push_logs pl {where}", params
            )
            total = cursor.fetchone()[0]

            offset = (page - 1) * page_size
            cursor = conn.execute(f"""
                SELECT pl.*, e.company_name, e.event_type
                FROM push_logs pl
                LEFT JOIN events e ON pl.event_id = e.id
                {where}
                ORDER BY pl.id DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset])
            items = [dict(row) for row in cursor.fetchall()]

        return items, total

    def mark_event_sent(self, event_id, channel="manual"):
        """标记事件已推送"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE events SET status='sent' WHERE id=?", (event_id,))
            conn.execute(
                "INSERT INTO push_logs (event_id, channel, status) VALUES (?, ?, 'success')",
                (event_id, channel)
            )
            conn.commit()

    # ====== 设置管理 ======

    @staticmethod
    def _init_default_settings(conn):
        """初始化默认设置（仅当没有记录时）"""
        try:
            from config import CONFIG
            default_webhook = CONFIG.get("wecom_webhook_url", "")
        except Exception:
            default_webhook = ""
        try:
            from config import CONFIG
            default_api_key = CONFIG.get("deepseek_api_key", "")
            default_api_url = CONFIG.get("deepseek_api_url", "https://api.deepseek.com")
            default_model = CONFIG.get("deepseek_model", "deepseek-chat")
        except Exception:
            default_api_key = ""
            default_api_url = "https://api.deepseek.com"
            default_model = "deepseek-chat"

        defaults = {
            "enabled_provinces": "广东",
            "excluded_cities": "深圳",
            "extra_cities": "",
            "wecom_webhook_url": default_webhook,
            "deepseek_api_key": default_api_key,
            "deepseek_api_url": default_api_url,
            "deepseek_model": default_model,
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )

    def get_setting(self, key):
        """获取单个设置"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def set_setting(self, key, value):
        """设置单个值"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()

    def get_all_settings(self):
        """获取所有设置"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT key, value FROM settings")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def update_settings(self, updates: dict):
        """批量更新设置"""
        with sqlite3.connect(self.db_path) as conn:
            for key, value in updates.items():
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, value)
                )
            conn.commit()

    def get_filter_config(self):
        """获取过滤配置（解析后的列表）"""
        raw = self.get_all_settings()
        return {
            "enabled_provinces": [
                p.strip() for p in raw.get("enabled_provinces", "广东").split(",") if p.strip()
            ],
            "excluded_cities": [
                c.strip() for c in raw.get("excluded_cities", "深圳").split(",") if c.strip()
            ],
            "extra_cities": [
                c.strip() for c in raw.get("extra_cities", "").split(",") if c.strip()
            ],
        }

    # ====== 爬虫历史 ======

    def start_crawl(self, source):
        """开始一次爬虫运行，返回 crawl_id"""
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO crawl_history (source, status, started_at) VALUES (?, 'running', ?)",
                (source, now)
            )
            conn.commit()
            return cursor.lastrowid

    def finish_crawl(self, crawl_id, status, items_fetched=0, error_msg=None):
        """完成一次爬虫运行"""
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE crawl_history SET status=?, items_fetched=?, error_msg=?, finished_at=? WHERE id=?",
                (status, items_fetched, error_msg, now, crawl_id)
            )
            conn.commit()

    def get_crawl_status(self, crawl_id):
        """查询爬虫运行状态"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM crawl_history WHERE id=?", (crawl_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_crawl_progress(self, crawl_id, message, pct):
        """追加一条进度信息到 crawl_history.progress"""
        import json, datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT progress FROM crawl_history WHERE id=?", (crawl_id,)
            )
            row = cursor.fetchone()
            logs = []
            if row and row[0]:
                try:
                    logs = json.loads(row[0])
                except (json.JSONDecodeError, TypeError):
                    logs = []
            logs.append({"message": message, "pct": pct, "time": now})
            conn.execute(
                "UPDATE crawl_history SET progress=? WHERE id=?",
                (json.dumps(logs, ensure_ascii=False), crawl_id)
            )
            conn.commit()

    def request_cancel_crawl(self, crawl_id):
        """请求取消正在运行的爬虫"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE crawl_history SET cancel_requested=1 WHERE id=?", (crawl_id,)
            )
            conn.commit()

    def is_crawl_cancelled(self, crawl_id):
        """检查爬虫是否被请求取消"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT cancel_requested FROM crawl_history WHERE id=?", (crawl_id,)
            )
            row = cursor.fetchone()
            return bool(row and row[0])

    def log_crawl(self, source, status, items_fetched=0, error_msg=None, started_at=None):
        """记录一次爬虫运行（旧接口，兼容）"""
        import datetime
        finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if started_at is None:
            started_at = finished_at
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO crawl_history (source, status, items_fetched, error_msg, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?)",
                (source, status, items_fetched, error_msg, started_at, finished_at)
            )
            conn.commit()

    def get_source_status(self):
        """各数据源最近运行状态"""
        sources = ["cninfo", "pitchhub", "gdgov", "ygp"]
        result = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for src in sources:
                cursor = conn.execute(
                    "SELECT * FROM crawl_history WHERE source=? ORDER BY id DESC LIMIT 1",
                    (src,)
                )
                row = cursor.fetchone()
                last_run = dict(row) if row else None
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM crawl_history WHERE source=? AND status='success'",
                    (src,)
                )
                success_count = cursor.fetchone()[0]
                result.append({
                    "source": src,
                    "last_run": last_run,
                    "success_count": success_count,
                })
        return result

    # ====== 完整采集流水线 ======

    def start_pipeline_run(self):
        """创建一条采集流水线运行记录"""
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO pipeline_runs (status, started_at) VALUES ('running', ?)",
                (now,)
            )
            conn.commit()
            return cursor.lastrowid

    def finish_pipeline_run(self, run_id, status, summary=None, error_msg=None):
        """完成一条采集流水线"""
        import json
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE pipeline_runs SET status=?, finished_at=datetime('now'), summary=?, error_msg=? WHERE id=?",
                (status, json.dumps(summary, ensure_ascii=False) if summary else None, error_msg, run_id)
            )
            conn.commit()

    def get_pipeline_runs(self, limit=10):
        """获取最近的流水线运行记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)
            )
            import json
            items = []
            for row in cursor.fetchall():
                item = dict(row)
                if item.get("summary"):
                    try:
                        item["summary"] = json.loads(item["summary"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                items.append(item)
            return items

    def get_latest_pipeline_run(self):
        """获取最近一条流水线运行记录"""
        runs = self.get_pipeline_runs(limit=1)
        return runs[0] if runs else None

    def get_crawl_history(self, page=1, page_size=20):
        """分页查询爬虫历史"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            offset = (page - 1) * page_size
            cursor = conn.execute(
                "SELECT COUNT(*) FROM crawl_history"
            )
            total = cursor.fetchone()[0]
            cursor = conn.execute(
                "SELECT * FROM crawl_history ORDER BY id DESC LIMIT ? OFFSET ?",
                [page_size, offset]
            )
            items = [dict(row) for row in cursor.fetchall()]
        return items, total

    def clear_all_events(self):
        """清空所有情报、推送记录、采集历史和流水线记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM events")
            conn.execute("DELETE FROM push_logs")
            conn.execute("DELETE FROM crawl_history")
            conn.execute("DELETE FROM pipeline_runs")
            conn.commit()

    def get_crawl_detail(self, crawl_id):
        """查询单条爬虫运行详情"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM crawl_history WHERE id=?", (crawl_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_events_by_crawl(self, crawl_record):
        """根据爬虫记录查找关联的事件（通过数据源和时间范围匹配）"""
        if not crawl_record:
            return []
        source = crawl_record.get("source", "")
        started_at = crawl_record.get("started_at", "")
        finished_at = crawl_record.get("finished_at", "")
        if not started_at:
            return []
        # crawl_history 的 source 与 events 表的 source 名称不同，需要映射
        source_map = {
            "cninfo": "巨潮资讯网",
            "pitchhub": "36氪融资快报",
            "gdgov": "广东省政府采购中心",
            "ygp": "广东省公共资源交易平台",
        }
        event_source = source_map.get(source, source)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if finished_at:
                cursor = conn.execute(
                    "SELECT * FROM events WHERE source=? AND created_at >= ? AND created_at <= ? ORDER BY id DESC",
                    (event_source, started_at, finished_at)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM events WHERE source=? AND created_at >= ? ORDER BY id DESC",
                    (event_source, started_at)
                )
            return [dict(row) for row in cursor.fetchall()]
