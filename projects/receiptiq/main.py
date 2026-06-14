"""ReceiptIQ entrypoint. Wires config -> storage -> sheets -> bot and starts polling."""
from __future__ import annotations

import logging
import os
import sys

from app.bot import build_application
from app.config import load_config
from app.sheets import Sheets
from app.storage import Store

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("receiptiq")


def main() -> int:
    try:
        cfg = load_config()
    except RuntimeError as e:
        log.error("Config error: %s", e)
        return 1

    store = Store(cfg.db_path)

    sheets: Sheets | None = None
    if cfg.spreadsheet_id and os.path.exists(cfg.google_creds_file):
        try:
            sheets = Sheets(cfg.google_creds_file, cfg.spreadsheet_id)
            log.info("Google Sheets connected.")
        except Exception as e:  # noqa: BLE001
            log.error("Sheets init failed (%s) — running in local-only mode.", e)
    else:
        log.warning("SPREADSHEET_ID or credentials missing — running in local-only mode.")

    log.info("Starting ReceiptIQ | provider=%s model=%s admins=%s", cfg.provider, cfg.model, cfg.admin_ids)
    app = build_application(cfg, store, sheets)
    app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
