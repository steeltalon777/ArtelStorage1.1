from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from ..db import get_db
from .pdf_service import PdfService
from .sync_outbox_service import SyncOutboxService


class OperationsService:
    """Service for warehouse operations and invoice generation."""

    VALID_TYPES = {"incoming", "issue", "writeoff", "move"}

    def __init__(self, db_path: Optional[str] = None):
        self.db = get_db(db_path)
        self.pdf_service = PdfService(db_path)
        self.sync_outbox_service = SyncOutboxService(db_path)

    def get_local_site(self) -> Dict:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, is_local FROM sites WHERE is_local = 1 ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                raise ValueError("Локальный склад не найден")
            return {"id": row["id"], "name": row["name"], "is_local": bool(row["is_local"]) }

    def list_sites(self, include_local: bool = True) -> List[Dict]:
        query = "SELECT id, name, is_local FROM sites"
        if not include_local:
            query += " WHERE is_local = 0"
        query += " ORDER BY name"

        with self.db.get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [{"id": r["id"], "name": r["name"], "is_local": bool(r["is_local"])} for r in rows]

    def create_or_get_site(self, site_name: str, is_local: bool = False) -> Dict:
        name = site_name.strip()
        if not name:
            raise ValueError("Название объекта не может быть пустым")

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, is_local FROM sites WHERE name = ?",
                (name,),
            ).fetchone()
            if row:
                return {"id": row["id"], "name": row["name"], "is_local": bool(row["is_local"])}

            cursor = conn.execute(
                "INSERT INTO sites (name, is_local) VALUES (?, ?)",
                (name, 1 if is_local else 0),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "name": name, "is_local": is_local}

    def get_item_catalog(self) -> List[Dict]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT i.id, i.name, i.unit, c.name as category_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                ORDER BY i.name
                """
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "unit": row["unit"],
                    "category_name": row["category_name"],
                }
                for row in rows
            ]

    def get_item_stock_on_site(self, item_id: UUID, site_id: int) -> float:
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN o.type = 'incoming' AND o.target_site_id = ? THEN ol.qty
                        WHEN o.type IN ('issue', 'writeoff') AND o.source_site_id = ? THEN -ol.qty
                        WHEN o.type = 'move' AND o.target_site_id = ? THEN ol.qty
                        WHEN o.type = 'move' AND o.source_site_id = ? THEN -ol.qty
                        ELSE 0
                    END
                ), 0) as qty
                FROM operation_lines ol
                JOIN operations o ON o.id = ol.operation_id
                WHERE ol.item_id = ?
                """,
                (site_id, site_id, site_id, site_id, item_id),
            ).fetchone()
            return float(row["qty"] if row else 0.0)

    def create_operation(
        self,
        operation_type: str,
        created_by: int,
        lines: List[Dict],
        recipient_name: Optional[str] = None,
        vehicle: Optional[str] = None,
        target_site_name: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> str:
        if operation_type not in self.VALID_TYPES:
            raise ValueError("Недопустимый тип операции")
        if not lines:
            raise ValueError("Добавьте хотя бы одну позицию ТМЦ")

        local_site = self.get_local_site()
        source_site_id = None
        target_site_id = None

        if operation_type == "incoming":
            target_site_id = local_site["id"]
        elif operation_type == "issue":
            source_site_id = local_site["id"]
            if not (recipient_name and recipient_name.strip()):
                raise ValueError("Для расхода обязательно укажите ФИО получателя")
            if not (vehicle and vehicle.strip()):
                raise ValueError("Для расхода обязательно укажите номер машины")
        elif operation_type == "writeoff":
            source_site_id = local_site["id"]
        elif operation_type == "move":
            source_site_id = local_site["id"]
            if not (target_site_name and target_site_name.strip()):
                raise ValueError("Для перемещения укажите объект получателя")
            if not (vehicle and vehicle.strip()):
                raise ValueError("Для перемещения укажите транспорт")
            target_site = self.create_or_get_site(target_site_name, is_local=False)
            if target_site["id"] == local_site["id"]:
                raise ValueError("Получатель перемещения должен быть отличен от локального склада")
            target_site_id = target_site["id"]

        normalized_lines = []
        for line in lines:
            item_id = line.get("item_id")
            qty = float(line.get("qty", 0))
            if not item_id or qty <= 0:
                raise ValueError("Для каждой позиции укажите ТМЦ и количество больше 0")
            normalized_lines.append({"item_id": UUID(str(item_id)), "qty": qty})

        if operation_type in {"issue", "writeoff", "move"}:
            self._ensure_sufficient_stock(source_site_id, normalized_lines)

        operation_id = uuid4()
        created_at = datetime.now()

        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO operations (
                    id, type, created_at, created_by, source_site_id, target_site_id,
                    recipient_name, vehicle, comment, pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    operation_type,
                    created_at,
                    created_by,
                    source_site_id,
                    target_site_id,
                    recipient_name,
                    vehicle,
                    comment,
                    None,
                ),
            )

            for line in normalized_lines:
                conn.execute(
                    "INSERT INTO operation_lines (operation_id, item_id, qty) VALUES (?, ?, ?)",
                    (operation_id, line["item_id"], line["qty"]),
                )

            self.sync_outbox_service.enqueue_operation_event(
                conn=conn,
                operation_id=operation_id,
                operation_type=operation_type,
                event_datetime=created_at,
                comment=comment,
                lines=normalized_lines,
            )

            conn.commit()

        if operation_type != "incoming":
            pdf_path = self._generate_invoice(operation_id)
            with self.db.get_connection() as conn:
                conn.execute("UPDATE operations SET pdf_path = ? WHERE id = ?", (pdf_path, operation_id))
                conn.commit()

        return str(operation_id)

    def list_recent_operations(self, limit: int = 15) -> List[Dict]:
        return self.list_operations(limit=limit)

    def list_operations(self, limit: int = 300, search: Optional[str] = None) -> List[Dict]:
        with self.db.get_connection() as conn:
            params: List = []
            where = ""
            if search and search.strip():
                pattern = f"%{search.strip()}%"
                where = (
                    "WHERE CAST(o.id AS TEXT) LIKE ? OR o.type LIKE ? OR COALESCE(u.full_name, u.username, '') LIKE ? "
                    "OR COALESCE(o.recipient_name, '') LIKE ? OR COALESCE(o.vehicle, '') LIKE ? "
                    "OR COALESCE(ss.name, '') LIKE ? OR COALESCE(ts.name, '') LIKE ?"
                )
                params.extend([pattern, pattern, pattern, pattern, pattern, pattern, pattern])

            params.append(limit)
            rows = conn.execute(
                f"""
                SELECT
                    o.id,
                    o.type,
                    o.created_at,
                    o.recipient_name,
                    o.vehicle,
                    o.comment,
                    o.pdf_path,
                    o.source_site_id,
                    o.target_site_id,
                    COALESCE(u.full_name, u.username) as author,
                    ss.name as source_site_name,
                    ts.name as target_site_name,
                    COUNT(ol.id) as lines_count
                FROM operations o
                LEFT JOIN users u ON u.id = o.created_by
                LEFT JOIN sites ss ON ss.id = o.source_site_id
                LEFT JOIN sites ts ON ts.id = o.target_site_id
                LEFT JOIN operation_lines ol ON ol.operation_id = o.id
                {where}
                GROUP BY o.id
                ORDER BY o.created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

            return [
                {
                    "id": row["id"],
                    "type": row["type"],
                    "created_at": row["created_at"],
                    "recipient_name": row["recipient_name"],
                    "vehicle": row["vehicle"],
                    "comment": row["comment"],
                    "pdf_path": row["pdf_path"],
                    "source_site_name": row["source_site_name"],
                    "target_site_name": row["target_site_name"],
                    "author": row["author"],
                    "lines_count": row["lines_count"],
                }
                for row in rows
            ]

    def get_operation_lines(self, operation_id: UUID) -> List[Dict]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT ol.item_id, ol.qty, i.name as item_name, i.unit
                FROM operation_lines ol
                LEFT JOIN items i ON i.id = ol.item_id
                WHERE ol.operation_id = ?
                """,
                (operation_id,),
            ).fetchall()
            return [
                {
                    "item_id": row["item_id"],
                    "qty": float(row["qty"]),
                    "item_name": row["item_name"],
                    "unit": row["unit"],
                }
                for row in rows
            ]

    def get_operation_by_id(self, operation_id: UUID) -> Optional[Dict]:
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    o.id,
                    o.type,
                    o.created_at,
                    o.recipient_name,
                    o.vehicle,
                    o.comment,
                    o.pdf_path,
                    ss.name as source_site_name,
                    ts.name as target_site_name
                FROM operations o
                LEFT JOIN sites ss ON ss.id = o.source_site_id
                LEFT JOIN sites ts ON ts.id = o.target_site_id
                WHERE o.id = ?
                """,
                (operation_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "id": row["id"],
                "type": row["type"],
                "created_at": row["created_at"],
                "recipient_name": row["recipient_name"],
                "vehicle": row["vehicle"],
                "comment": row["comment"],
                "pdf_path": row["pdf_path"],
                "source_site_name": row["source_site_name"],
                "target_site_name": row["target_site_name"],
            }

    def _ensure_sufficient_stock(self, source_site_id: int, lines: List[Dict]):
        for line in lines:
            available = self.get_item_stock_on_site(line["item_id"], source_site_id)
            if available < line["qty"]:
                raise ValueError(
                    f"Недостаточно остатка по ТМЦ {line['item_id']}: доступно {available:g}, требуется {line['qty']:g}"
                )

    def _generate_invoice(self, operation_id: UUID) -> str:
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, type, created_at, recipient_name, vehicle
                FROM operations
                WHERE id = ?
                """,
                (operation_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Операция не найдена для генерации накладной")

        lines = self.get_operation_lines(operation_id)
        invoice_lines = [
            {
                "item_name": line["item_name"],
                "qty": line["qty"],
                "unit": line["unit"],
            }
            for line in lines
        ]

        return self.pdf_service.generate_invoice(
            operation_type=row["type"],
            operation_id=str(row["id"]),
            created_at=row["created_at"] if isinstance(row["created_at"], datetime) else datetime.now(),
            lines=invoice_lines,
            recipient_name=row["recipient_name"],
            vehicle=row["vehicle"],
        )
