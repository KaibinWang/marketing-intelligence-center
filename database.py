"""数据库操作 - 存储和查询情报事件"""
import sqlite3
import json
import os
from datetime import datetime


class IntelligenceDB:
    """情报数据库"""

    def __init__(self, db_path="./data/intelligence.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    company_name TEXT,
                    stock_code TEXT,
                    project_or_subject TEXT,
                    amount_estimate INTEGER DEFAULT 0,
                    purchaser TEXT,
                    pub_date TEXT,
                    source TEXT,
                    source_url TEXT UNIQUE,
                    detail_text TEXT,
                    marketing_suggestion TEXT,
                    status TEXT DEFAULT 'new',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_company
                ON events(company_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON events(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type
                ON events(event_type)
            """)
            conn.commit()

    def exists(self, source_url):
        """检查事件是否已存在

        Args:
            source_url: 原文链接

        Returns:
            bool: True=已存在，False=不存在
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM events WHERE source_url=?",
                (source_url,)
            )
            return cursor.fetchone() is not None

    def save_event(self, event, detail_text="", marketing_suggestion="", source_url="", status="new"):
        """保存事件

        Args:
            event: 事件信息dict
            detail_text: 公告详情正文
            marketing_suggestion: AI生成的营销建议
            source_url: 原文链接（用于去重）
            status: 状态（new/sent/filtered），默认 new

        Returns:
            int|None: 新插入的事件id，已存在则返回 None
        """
        url = source_url or event.get("source_url", "")
        if not url:
            return False

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute("""
                    INSERT INTO events
                    (event_type, company_name, stock_code, project_or_subject,
                     amount_estimate, purchaser, pub_date, source, source_url,
                     detail_text, marketing_suggestion, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.get("event_type", "其他"),
                    event.get("company_name", ""),
                    event.get("stock_code", ""),
                    event.get("project_or_subject", ""),
                    event.get("amount_estimate", 0),
                    event.get("purchaser", ""),
                    event.get("pub_date", ""),
                    event.get("source", ""),
                    url,
                    detail_text,
                    marketing_suggestion,
                    status,
                    now,
                ))
                event_id = cursor.lastrowid
                conn.commit()
                return event_id
            except sqlite3.IntegrityError:
                return False

    def get_new_events(self, limit=50):
        """获取未处理的新事件"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM events WHERE status='new' ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def mark_sent(self, event_id):
        """标记事件已推送"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE events SET status='sent' WHERE id=?",
                (event_id,)
            )
            conn.commit()

    def get_today_count(self):
        """获取今日新增事件数"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM events WHERE date(created_at)=date('now')"
            )
            return cursor.fetchone()[0]

    def get_stats(self):
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) as new_count,
                    SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) as sent_count,
                    COUNT(DISTINCT company_name) as company_count
                FROM events
            """)
            row = cursor.fetchone()
            return {
                "total": row[0] or 0,
                "new": row[1] or 0,
                "sent": row[2] or 0,
                "companies": row[3] or 0,
            }
