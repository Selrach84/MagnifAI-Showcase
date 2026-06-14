"""Google Sheets sink. One worksheet (tab) per client inside one spreadsheet.

Uses a Google service account. Share the target spreadsheet with the service
account email (found in service_account.json) as Editor.
"""
from __future__ import annotations

import logging

import gspread
from google.oauth2.service_account import Credentials

from .models import Receipt

log = logging.getLogger("receiptiq.sheets")

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_HEADER = [
    "Date", "Merchant", "Category", "Subtotal", "Tax", "Tip",
    "Total", "Currency", "Payment", "Items", "Confidence", "ReceiptID",
]


class Sheets:
    def __init__(self, creds_file: str, spreadsheet_id: str):
        creds = Credentials.from_service_account_file(creds_file, scopes=_SCOPES)
        self._gc = gspread.authorize(creds)
        self._ss = self._gc.open_by_key(spreadsheet_id)
        self._tabs: dict[str, gspread.Worksheet] = {}

    def _worksheet(self, tab: str) -> gspread.Worksheet:
        if tab in self._tabs:
            return self._tabs[tab]
        try:
            ws = self._ss.worksheet(tab)
        except gspread.WorksheetNotFound:
            ws = self._ss.add_worksheet(title=tab, rows=1000, cols=len(_HEADER))
            ws.append_row(_HEADER, value_input_option="USER_ENTERED")
        self._tabs[tab] = ws
        return ws

    def append(self, tab: str, receipt_id: str, r: Receipt) -> None:
        items = "; ".join(
            f"{li.description} x{li.qty or 1} = {li.amount}" for li in r.line_items
        )[:5000]
        row = [
            r.date.isoformat() if r.date else "",
            r.merchant,
            r.category.value,
            str(r.subtotal or ""),
            str(r.tax or ""),
            str(r.tip or ""),
            str(r.total or ""),
            r.currency,
            r.payment_method or "",
            items,
            f"{int(r.confidence * 100)}%",
            receipt_id,
        ]
        self._worksheet(tab).append_row(row, value_input_option="USER_ENTERED")
        log.info("appended receipt %s to tab %s", receipt_id, tab)
