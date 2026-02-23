from typing import Dict, List, Optional

from ..db import get_db


class StockService:
    """Service for stock balances with search/sort/filter support."""

    def __init__(self, db_path: Optional[str] = None):
        self.db = get_db(db_path)

    def get_local_site_id(self) -> Optional[int]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT id FROM sites WHERE is_local = 1 ORDER BY id LIMIT 1").fetchone()
            return int(row["id"]) if row else None

    def get_stock_rows(
        self,
        site_id: Optional[int] = None,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
    ) -> List[Dict]:
        with self.db.get_connection() as conn:
            where_clauses = []
            params: List = []

            if search and search.strip():
                pattern = f"%{search.strip()}%"
                where_clauses.append("(i.name LIKE ? OR CAST(i.id AS TEXT) LIKE ? OR COALESCE(c.name, '') LIKE ?)")
                params.extend([pattern, pattern, pattern])

            if category_id is not None:
                where_clauses.append("i.category_id = ?")
                params.append(category_id)

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            if site_id is None:
                qty_expr = (
                    "COALESCE(SUM(CASE "
                    "WHEN o.type = 'incoming' THEN ol.qty "
                    "WHEN o.type IN ('issue', 'writeoff') THEN -ol.qty "
                    "WHEN o.type = 'move' THEN 0 "
                    "ELSE 0 END), 0)"
                )
                qty_params = []
            else:
                qty_expr = (
                    "COALESCE(SUM(CASE "
                    "WHEN o.type = 'incoming' AND o.target_site_id = ? THEN ol.qty "
                    "WHEN o.type IN ('issue', 'writeoff') AND o.source_site_id = ? THEN -ol.qty "
                    "WHEN o.type = 'move' AND o.target_site_id = ? THEN ol.qty "
                    "WHEN o.type = 'move' AND o.source_site_id = ? THEN -ol.qty "
                    "ELSE 0 END), 0)"
                )
                qty_params = [site_id, site_id, site_id, site_id]

            rows = conn.execute(
                f"""
                SELECT
                    i.id,
                    i.name,
                    i.unit,
                    i.category_id,
                    c.name as category_name,
                    {qty_expr} as qty
                FROM items i
                LEFT JOIN categories c ON c.id = i.category_id
                LEFT JOIN operation_lines ol ON ol.item_id = i.id
                LEFT JOIN operations o ON o.id = ol.operation_id
                {where_sql}
                GROUP BY i.id, i.name, i.unit, i.category_id, c.name
                ORDER BY i.name
                """,
                qty_params + params,
            ).fetchall()

            return [
                {
                    "item_id": row["id"],
                    "name": row["name"],
                    "unit": row["unit"],
                    "category_id": row["category_id"],
                    "category_name": row["category_name"],
                    "qty": float(row["qty"]),
                }
                for row in rows
            ]
