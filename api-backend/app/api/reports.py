"""
api/reports.py - downloadable and emailable operational reports.
"""
from __future__ import annotations

import html
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_current_user, get_db
from ..core.config import settings
from ..models.auth import User

router = APIRouter(prefix="/reports", tags=["Reports"])

ReportType = Literal["executive", "inventory", "supplier", "logistics", "forecast"]


class ReportEmailRequest(BaseModel):
    email: EmailStr
    report_type: ReportType = "executive"
    format: Literal["html", "csv"] = "html"


class ReportEmailResponse(BaseModel):
    sent: bool
    status: str
    report_type: str
    email: str
    outbox_path: Optional[str] = None


def _report_title(report_type: str) -> str:
    return {
        "executive": "Executive Operations Report",
        "inventory": "Inventory Health Report",
        "supplier": "Supplier Scorecard Report",
        "logistics": "Logistics SLA Report",
        "forecast": "Sales Forecast Report",
    }.get(report_type, "Operations Report")


async def _report_metrics(db: AsyncSession) -> dict:
    sales = (
        await db.execute(
            text(
                """
                SELECT COUNT(*) AS sales_orders,
                       COALESCE(SUM(quantity), 0) AS units_sold,
                       COALESCE(SUM(final_amount), 0) AS revenue
                FROM sales
                """
            )
        )
    ).mappings().one()
    inventory = (
        await db.execute(
            text(
                """
                SELECT COUNT(*) AS inventory_rows,
                       COALESCE(SUM(current_stock), 0) AS stock_units,
                       COALESCE(SUM(reserved_stock), 0) AS reserved_units,
                       COALESCE(SUM(incoming_stock), 0) AS incoming_units,
                       SUM(CASE WHEN current_stock < safety_stock THEN 1 ELSE 0 END) AS low_stock_rows
                FROM inventory
                """
            )
        )
    ).mappings().one()
    logistics = (
        await db.execute(
            text(
                """
                SELECT COUNT(*) AS shipments,
                       SUM(CASE
                            WHEN delayed_flag = 1
                              OR (actual_delivery_days IS NOT NULL
                                  AND expected_delivery_days IS NOT NULL
                                  AND actual_delivery_days > expected_delivery_days)
                            THEN 1 ELSE 0 END) AS delayed_shipments,
                       COALESCE(AVG(actual_delivery_days), 0) AS avg_delivery_days
                FROM shipments
                """
            )
        )
    ).mappings().one()
    procurement = (
        await db.execute(
            text(
                """
                SELECT COUNT(*) AS purchase_orders,
                       COALESCE(SUM(quantity * unit_cost), 0) AS po_spend
                FROM purchase_orders
                """
            )
        )
    ).mappings().one()
    returns = (
        await db.execute(
            text(
                """
                SELECT COUNT(*) AS returns,
                       SUM(CASE WHEN fraud_risk_score >= 0.65 THEN 1 ELSE 0 END) AS high_risk_returns
                FROM returns
                """
            )
        )
    ).mappings().one()
    forecast = (
        await db.execute(
            text(
                """
                SELECT COALESCE(SUM(predicted_qty), 0) AS forecast_units,
                       COUNT(DISTINCT product_id) AS forecast_products,
                       MIN(forecast_date) AS forecast_start,
                       MAX(forecast_date) AS forecast_end
                FROM sales_forecasts
                """
            )
        )
    ).mappings().one()

    metrics = {
        **dict(sales),
        **dict(inventory),
        **dict(logistics),
        **dict(procurement),
        **dict(returns),
        **dict(forecast),
    }
    shipments = int(metrics.get("shipments") or 0)
    delayed = int(metrics.get("delayed_shipments") or 0)
    inventory_rows = int(metrics.get("inventory_rows") or 0)
    low_stock = int(metrics.get("low_stock_rows") or 0)
    metrics["delay_rate_pct"] = round(delayed / shipments * 100, 2) if shipments else 0
    metrics["inventory_health_pct"] = round((inventory_rows - low_stock) / inventory_rows * 100, 2) if inventory_rows else 0
    sales_orders = int(metrics.get("sales_orders") or 0)
    returns_count = int(metrics.get("returns") or 0)
    metrics["return_rate_pct"] = round(returns_count / sales_orders * 100, 2) if sales_orders else 0
    return metrics


async def _report_rows(db: AsyncSession, report_type: str) -> list[dict]:
    if report_type == "inventory":
        sql = """
            SELECT p.product_name, p.sku, i.warehouse_id, i.current_stock,
                   i.reserved_stock, i.incoming_stock, i.safety_stock
            FROM inventory i
            JOIN products p ON p.product_id = i.product_id
            ORDER BY i.current_stock ASC
        """
    elif report_type == "supplier":
        sql = """
            SELECT supplier_name, city, avg_lead_time_days AS avg_delivery_time_days, reliability_score,
                   defect_rate, on_time_delivery_rate
            FROM suppliers
            ORDER BY reliability_score DESC
        """
    elif report_type == "logistics":
        sql = """
            SELECT shipment_code, shipment_type, logistics_provider, source_city,
                   destination_city, expected_delivery_days, actual_delivery_days,
                   delayed_flag, shipment_status
            FROM shipments
            ORDER BY shipment_id DESC
        """
    elif report_type == "forecast":
        sql = """
            SELECT p.product_name, p.sku, sf.forecast_date,
                   ROUND(sf.predicted_qty, 0) AS expected_demand,
                   ROUND(sf.lower_qty, 0) AS low_case,
                   ROUND(sf.upper_qty, 0) AS high_case,
                   sf.stockout_in_days, sf.model_used
            FROM sales_forecasts sf
            JOIN products p ON p.product_id = sf.product_id
            ORDER BY sf.forecast_date ASC, sf.predicted_qty DESC
        """
    else:
        sql = """
            SELECT p.product_name, p.sku, COUNT(s.sale_id) AS orders,
                   COALESCE(SUM(s.quantity), 0) AS units_sold,
                   COALESCE(SUM(s.final_amount), 0) AS revenue
            FROM products p
            LEFT JOIN sales s ON s.product_id = p.product_id
            GROUP BY p.product_id
            ORDER BY revenue DESC
        """
    return [dict(row) for row in (await db.execute(text(sql))).mappings().all()]


def _chart_series(report_type: str, rows: list[dict]) -> list[tuple[str, float]]:
    if not rows:
        return []
    if report_type == "forecast":
        grouped: dict[str, float] = {}
        for row in rows:
            label = str(row.get("forecast_date") or "Unknown")
            grouped[label] = grouped.get(label, 0.0) + float(row.get("expected_demand") or 0)
        return list(grouped.items())[:12]

    candidates = {
        "executive": ("product_name", "revenue"),
        "inventory": ("product_name", "current_stock"),
        "supplier": ("supplier_name", "reliability_score"),
        "logistics": ("shipment_code", "actual_delivery_days"),
    }
    label_key, value_key = candidates.get(report_type, ("product_name", "revenue"))
    return [
        (str(row.get(label_key) or "Item")[:24], float(row.get(value_key) or 0))
        for row in rows[:10]
    ]


def _build_svg_chart(report_type: str, rows: list[dict]) -> str:
    series = _chart_series(report_type, rows)
    if not series:
        return "<div class='empty'>No chart data available for this report.</div>"
    width = 760
    height = 260
    padding_left = 48
    padding_bottom = 48
    chart_width = width - padding_left - 24
    chart_height = height - 42 - padding_bottom
    max_value = max(value for _, value in series) or 1
    bar_gap = 8
    bar_width = max(16, (chart_width - bar_gap * (len(series) - 1)) / len(series))
    bars = []
    labels = []
    for idx, (label, value) in enumerate(series):
        bar_height = (value / max_value) * chart_height
        x = padding_left + idx * (bar_width + bar_gap)
        y = 32 + chart_height - bar_height
        bars.append(
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_width:.1f}' height='{bar_height:.1f}' "
            "rx='5' fill='#1f7a6d' />"
            f"<text x='{x + bar_width / 2:.1f}' y='{max(18, y - 6):.1f}' "
            "text-anchor='middle' font-size='10' fill='#344054'>"
            f"{html.escape(f'{value:,.0f}')}</text>"
        )
        labels.append(
            f"<text x='{x + bar_width / 2:.1f}' y='{height - 22}' text-anchor='middle' "
            "font-size='9' fill='#667085'>"
            f"{html.escape(label[:12])}</text>"
        )
    chart_title = "Expected Demand by Date" if report_type == "forecast" else "Report Snapshot"
    return (
        f"<h2>{chart_title}</h2>"
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{html.escape(chart_title)}'>"
        "<rect width='100%' height='100%' rx='12' fill='#f8fafc' />"
        f"<line x1='{padding_left}' y1='{32 + chart_height}' x2='{width - 18}' y2='{32 + chart_height}' stroke='#d0d5dd' />"
        f"<line x1='{padding_left}' y1='32' x2='{padding_left}' y2='{32 + chart_height}' stroke='#d0d5dd' />"
        f"{''.join(bars)}{''.join(labels)}</svg>"
    )


def _report_summary(report_type: str, metrics: dict, rows: list[dict]) -> list[str]:
    title = _report_title(report_type)
    return [
        f"{title} generated from live operational data with {len(rows):,} detail row(s).",
        f"Revenue is INR {float(metrics.get('revenue') or 0):,.0f} across {int(metrics.get('sales_orders') or 0):,} sales orders.",
        f"Inventory health is {float(metrics.get('inventory_health_pct') or 0):.1f}% with {int(metrics.get('low_stock_rows') or 0):,} low-stock row(s).",
        f"Returns total {int(metrics.get('returns') or 0):,}, giving a return rate of {float(metrics.get('return_rate_pct') or 0):.2f}%.",
        f"Logistics delay rate is {float(metrics.get('delay_rate_pct') or 0):.1f}% across {int(metrics.get('shipments') or 0):,} shipment records.",
    ]


def _build_html_report(report_type: str, metrics: dict, rows: list[dict]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = _report_title(report_type)
    cards = [
        ("Revenue", f"INR {float(metrics.get('revenue') or 0):,.0f}"),
        ("Sales orders", f"{int(metrics.get('sales_orders') or 0):,}"),
        ("Forecast units", f"{float(metrics.get('forecast_units') or 0):,.0f}"),
        ("Inventory health", f"{float(metrics.get('inventory_health_pct') or 0):.1f}%"),
        ("Delay rate", f"{float(metrics.get('delay_rate_pct') or 0):.1f}%"),
        ("High-risk returns", f"{int(metrics.get('high_risk_returns') or 0):,}"),
    ]
    headers = list(rows[0].keys()) if rows else []
    table_head = "".join(f"<th>{html.escape(str(header).replace('_', ' ').title())}</th>" for header in headers)
    table_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(header, '')))}</td>" for header in headers) + "</tr>"
        for row in rows
    )
    card_html = "".join(f"<div class='card'><span>{label}</span><strong>{value}</strong></div>" for label, value in cards)
    summary_html = "".join(f"<li>{html.escape(line)}</li>" for line in _report_summary(report_type, metrics, rows))
    chart_html = _build_svg_chart(report_type, rows)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #17202a; margin: 32px; }}
    header {{ border-bottom: 3px solid #1f7a6d; padding-bottom: 16px; margin-bottom: 24px; }}
    h1 {{ margin: 0; font-size: 28px; }}
    .meta {{ color: #667085; margin-top: 6px; }}
    .summary {{ border: 1px solid #d0d5dd; border-radius: 10px; background: #f8fafc; padding: 16px 18px; margin: 20px 0; }}
    .summary h2 {{ margin: 0 0 10px; font-size: 18px; }}
    .summary ul {{ margin: 0; padding-left: 20px; color: #344054; line-height: 1.5; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 24px 0; }}
    .card {{ border: 1px solid #d0d5dd; border-radius: 8px; padding: 14px; background: #f8fafc; }}
    .card span {{ display: block; color: #667085; font-size: 12px; }}
    .card strong {{ display: block; margin-top: 6px; font-size: 18px; }}
    svg {{ width: 100%; height: auto; margin: 8px 0 20px; }}
    .empty {{ border: 1px dashed #d0d5dd; border-radius: 8px; padding: 16px; color: #667085; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 12px; }}
    th, td {{ border: 1px solid #e4e7ec; padding: 8px; text-align: left; }}
    th {{ background: #ecfdf3; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="meta">Generated by AI Inventory Copilot at {generated_at}</div>
  </header>
  <section class="summary">
    <h2>Summary</h2>
    <ul>{summary_html}</ul>
  </section>
  <section class="grid">{card_html}</section>
  {chart_html}
  <h2>Report Details</h2>
  <table><thead><tr>{table_head}</tr></thead><tbody>{table_rows}</tbody></table>
</body>
</html>"""


def _build_csv_report(metrics: dict, rows: list[dict]) -> str:
    lines = ["section,key,value"]
    for key, value in metrics.items():
        lines.append(f"metric,{key},{value}")
    if rows:
        headers = list(rows[0].keys())
        lines.append("")
        lines.append(",".join(headers))
        for row in rows:
            lines.append(",".join('"' + str(row.get(header, "")).replace('"', '""') + '"' for header in headers))
    return "\n".join(lines)


@router.get("/download")
async def download_report(
    report_type: ReportType = Query("executive"),
    format: Literal["html", "csv"] = Query("html"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    metrics = await _report_metrics(db)
    rows = await _report_rows(db, report_type)
    filename = f"{report_type}-report-{datetime.now().strftime('%Y%m%d-%H%M')}.{format}"
    if format == "csv":
        content = _build_csv_report(metrics, rows)
        return Response(
            content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    content = _build_html_report(report_type, metrics, rows)
    return Response(
        content,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/email", response_model=ReportEmailResponse)
async def email_report(
    payload: ReportEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metrics = await _report_metrics(db)
    rows = await _report_rows(db, payload.report_type)
    body = _build_html_report(payload.report_type, metrics, rows)
    subject = _report_title(payload.report_type)

    if settings.smtp_host:
        message = EmailMessage()
        message["From"] = settings.smtp_from_email or current_user.email
        message["To"] = str(payload.email)
        message["Subject"] = subject
        message.set_content("Your report is attached as HTML.")
        message.add_alternative(body, subtype="html")
        message.add_attachment(
            body.encode("utf-8"),
            maintype="text",
            subtype="html",
            filename=f"{payload.report_type}-report.html",
        )
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return ReportEmailResponse(
            sent=True,
            status="sent_via_smtp",
            report_type=payload.report_type,
            email=str(payload.email),
        )

    outbox = Path("generated-reports") / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    outbox_file = outbox / f"{payload.report_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.eml"
    outbox_file.write_text(
        "\n".join(
            [
                f"From: {current_user.email}",
                f"To: {payload.email}",
                f"Subject: {subject}",
                "Content-Type: text/html; charset=utf-8",
                "",
                body,
            ]
        ),
        encoding="utf-8",
    )

    if not outbox_file.exists():
        raise HTTPException(status_code=500, detail="Report email could not be queued.")

    return ReportEmailResponse(
        sent=False,
        status="smtp_not_configured_queued_to_local_outbox",
        report_type=payload.report_type,
        email=str(payload.email),
        outbox_path=str(outbox_file),
    )
