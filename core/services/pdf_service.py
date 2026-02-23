from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class PdfService:
    """Generates immutable invoice PDFs for non-incoming operations."""

    def __init__(self, db_path: Optional[str] = None):
        base_dir = Path(db_path).resolve().parent if db_path else (Path(__file__).resolve().parents[2] / "db")
        self.pdf_dir = base_dir / "pdf"
        self.pdf_dir.mkdir(parents=True, exist_ok=True)

    def generate_invoice(
        self,
        operation_type: str,
        operation_id: str,
        created_at: datetime,
        lines: List[Dict],
        recipient_name: Optional[str] = None,
        vehicle: Optional[str] = None,
    ) -> str:
        try:
            from PyQt6.QtCore import QMarginsF, QRectF, Qt
            from PyQt6.QtGui import QFont, QFontMetrics, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen
        except Exception as exc:
            raise RuntimeError("Для генерации накладной требуется установленный пакет PyQt6") from exc

        filename = f"invoice_{operation_type}_{operation_id}.pdf"
        target = self.pdf_dir / filename

        writer = QPdfWriter(str(target))
        writer.setResolution(300)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageLayout(
            QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(20.0, 20.0, 15.0, 20.0),
            )
        )

        painter = QPainter(writer)
        try:
            self._draw_invoice(
                painter,
                writer,
                QRectF,
                Qt,
                QFont,
                QFontMetrics,
                QPen,
                operation_type,
                operation_id,
                created_at,
                lines,
                recipient_name,
                vehicle,
            )
        finally:
            painter.end()

        return str(target)

    def _draw_invoice(
        self,
        painter,
        writer,
        QRectF,
        Qt,
        QFont,
        QFontMetrics,
        QPen,
        operation_type: str,
        operation_id: str,
        created_at: datetime,
        lines: List[Dict],
        recipient_name: Optional[str],
        vehicle: Optional[str],
    ):
        type_label = {
            "issue": "Расход (выдача)",
            "writeoff": "Списание",
            "move": "Перемещение",
            "incoming": "Приход",
        }.get(operation_type, operation_type)

        page_w = writer.width()
        page_h = writer.height()
        mm = lambda value: self._mm_to_px(value, writer.resolution())

        left = mm(20)
        right = mm(15)
        top = mm(20)
        bottom = mm(20)
        content_w = page_w - left - right

        doc_number = self._build_doc_number(operation_id=operation_id, created_at=created_at)
        doc_date = created_at.strftime("%d.%m.%Y")
        recipient_label = recipient_name if recipient_name else "-"
        vehicle_label = vehicle if vehicle else "-"

        y = top

        title_font = QFont("Arial", 16, QFont.Weight.Bold)
        body_font = QFont("Arial", 12)

        painter.setFont(title_font)
        title_metrics = QFontMetrics(title_font)
        title_h = title_metrics.ascent() + title_metrics.descent() + title_metrics.leading()
        safe_title_h = int(title_h * 1.3)
        painter.drawText(
            QRectF(left, y, content_w, safe_title_h),
            int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
            f"Накладная №{doc_number} от {doc_date}г",
        )

        y += safe_title_h + mm(4)
        painter.setFont(body_font)
        org_metrics = QFontMetrics(body_font)
        org_h = org_metrics.ascent() + org_metrics.descent() + org_metrics.leading()
        safe_org_h = int(org_h * 1.3)
        painter.drawText(
            QRectF(left, y, content_w, safe_org_h),
            int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
            "ООО АС «Горизонт»",
        )

        y += safe_org_h + mm(10)
        painter.drawText(left, y, f"Основание для отпуска: {type_label}")
        y += mm(5)
        painter.drawText(left, y, f"Получатель: {recipient_label}")
        y += mm(5)
        painter.drawText(left, y, f"Транспорт: {vehicle_label}")

        y += mm(10)
        table_bottom_y = self._draw_table_paginated(
            painter,
            writer,
            QRectF,
            Qt,
            QFont,
            QFontMetrics,
            QPen,
            left,
            y,
            top,
            bottom,
            page_h,
            lines,
        )

        self._draw_signatures(
            painter,
            writer,
            QRectF,
            Qt,
            QFont,
            QFontMetrics,
            left,
            top,
            bottom,
            page_h,
            table_bottom_y,
        )

    def _draw_table_paginated(
        self,
        painter,
        writer,
        QRectF,
        Qt,
        QFont,
        QFontMetrics,
        QPen,
        left: int,
        start_y: int,
        top: int,
        bottom: int,
        page_h: int,
        lines: List[Dict],
    ) -> int:
        mm = lambda value: self._mm_to_px(value, writer.resolution())
        col_widths = [mm(15), mm(95), mm(25), mm(40)]
        headers = ["№", "Наименование ТМЦ", "Ед. изм", "Кол-во"]
        min_row_h = mm(9.5)
        cell_pad = mm(2.0)
        min_remaining_before_break = mm(30)

        table_font = QFont("Arial", 11)
        header_font = QFont("Arial", 11, QFont.Weight.Bold)
        header_metrics = QFontMetrics(header_font)
        header_text_h = header_metrics.ascent() + header_metrics.descent()
        header_h = int(header_text_h * 1.8)
        metrics = QFontMetrics(table_font)

        grid_pen = QPen()
        grid_pen.setWidthF(0.9)

        def draw_table_header(current_y: int) -> int:
            painter.setPen(grid_pen)
            painter.setFont(header_font)
            current_x = left
            for idx, text in enumerate(headers):
                width = col_widths[idx]
                painter.drawRect(int(current_x), int(current_y), int(width), int(header_h))
                painter.drawText(
                    QRectF(current_x + cell_pad, current_y + cell_pad, width - 2 * cell_pad, header_h - 2 * cell_pad + 2),
                    int(Qt.AlignmentFlag.AlignCenter),
                    text,
                )
                current_x += width
            return current_y + header_h

        current_y = draw_table_header(start_y)
        painter.setFont(table_font)

        for index, line in enumerate(lines, start=1):
            row_values = [
                str(index),
                str(line.get("item_name", "")),
                str(line.get("unit", "")),
                f"{float(line.get('qty', 0)):g}",
            ]

            name_rect = QRectF(0, 0, col_widths[1] - 2 * cell_pad, 100000)
            name_height = metrics.boundingRect(
                name_rect.toRect(),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap),
                row_values[1],
            ).height()
            row_h = max(min_row_h, int(name_height + 2 * cell_pad))

            remaining_to_bottom = (page_h - bottom) - current_y
            if remaining_to_bottom < max(min_remaining_before_break, row_h):
                writer.newPage()
                current_y = draw_table_header(top)
                painter.setFont(table_font)

            current_x = left
            for col_idx, value in enumerate(row_values):
                width = col_widths[col_idx]
                painter.setPen(grid_pen)
                painter.drawRect(int(current_x), int(current_y), int(width), int(row_h))

                if col_idx == 1:
                    align = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap)
                elif col_idx == 0:
                    align = int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                else:
                    align = int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

                painter.drawText(
                    QRectF(current_x + cell_pad, current_y + cell_pad, width - 2 * cell_pad, row_h - 2 * cell_pad),
                    align,
                    value,
                )
                current_x += width

            current_y += row_h

        return current_y

    def _draw_signatures(
        self,
        painter,
        writer,
        QRectF,
        Qt,
        QFont,
        QFontMetrics,
        left: int,
        top: int,
        bottom: int,
        page_h: int,
        table_bottom_y: int,
    ):
        mm = lambda value: self._mm_to_px(value, writer.resolution())
        body_font = QFont("Arial", 11)
        painter.setFont(body_font)

        gap_after_table = mm(10)
        line_gap = mm(6)
        block_gap = mm(10)
        bottom_clearance = mm(25)

        sig2_role_y = page_h - bottom_clearance
        sig2_line_y = sig2_role_y - line_gap
        sig1_role_y = sig2_line_y - block_gap
        sig1_line_y = sig1_role_y - line_gap

        required_top_y = sig1_line_y
        if table_bottom_y + gap_after_table > required_top_y:
            writer.newPage()
            sig2_role_y = page_h - bottom_clearance
            sig2_line_y = sig2_role_y - line_gap
            sig1_role_y = sig2_line_y - block_gap
            sig1_line_y = sig1_role_y - line_gap

        painter.drawText(left, sig1_line_y, "Отпуск разрешил: _____________________")
        painter.drawText(left, sig1_role_y, "Начальник базы")
        painter.drawText(left, sig2_line_y, "Отпустил: ____________________________")
        painter.drawText(left, sig2_role_y, "Кладовщик")

    def _build_doc_number(self, operation_id: str, created_at: datetime) -> str:
        safe_id = str(operation_id).replace("-", "").upper()
        return f"{created_at.strftime('%Y%m%d')}-{safe_id[:6]}"

    @staticmethod
    def _mm_to_px(mm_value: float, dpi: int) -> int:
        return int(round(mm_value * dpi / 25.4))
