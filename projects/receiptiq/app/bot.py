"""Telegram bot: the client-facing surface.

Client flow:  send receipt photo -> bot extracts -> shows summary -> client taps
✅ Save (writes to their Google Sheet) or 🗑 Discard.

Admin flow:  /adduser, /clients, /removeuser, /sync, /whoami  (admins only).
"""
from __future__ import annotations

import hashlib
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .categorize import categorize
from .config import Config
from .extractor import ExtractionError, extract
from .sheets import Sheets
from .storage import Store

log = logging.getLogger("receiptiq.bot")


# --- helpers ---------------------------------------------------------------

def _cfg(ctx: ContextTypes.DEFAULT_TYPE) -> Config:
    return ctx.application.bot_data["cfg"]


def _store(ctx: ContextTypes.DEFAULT_TYPE) -> Store:
    return ctx.application.bot_data["store"]


def _sheets(ctx: ContextTypes.DEFAULT_TYPE) -> Sheets | None:
    return ctx.application.bot_data.get("sheets")


def _is_admin(ctx: ContextTypes.DEFAULT_TYPE, tg_id: int) -> bool:
    return tg_id in _cfg(ctx).admin_ids


# --- client commands -------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    client = _store(ctx).get_client(uid)
    if client:
        await update.message.reply_text(
            f"Welcome back, {client['name']}! \U0001F44B\n\n"
            "Just send me a *photo of any receipt* and I'll log it to your expense sheet automatically.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            "Hi! This is the *MagnifAI ReceiptIQ* bot.\n\n"
            f"You're not registered yet. Send your Telegram ID to MagnifAI to get set up:\n`{uid}`",
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_whoami(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Your Telegram ID: `{update.effective_user.id}`", parse_mode=ParseMode.MARKDOWN)


# --- photo handler ---------------------------------------------------------

async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    store = _store(ctx)
    client = store.get_client(uid)
    if not client:
        await update.message.reply_text(
            "You're not registered. Send `/start` and share your ID with MagnifAI.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Highest-resolution photo Telegram offers, or a document/image.
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
        file_id = update.message.document.file_id
    if not file_id:
        await update.message.reply_text("Please send a photo or image file of the receipt.")
        return

    status = await update.message.reply_text("\U0001F50D Reading receipt…")
    try:
        tg_file = await ctx.bot.get_file(file_id)
        image_bytes = bytes(await tg_file.download_as_bytearray())
    except Exception as e:  # noqa: BLE001
        log.exception("download failed")
        await status.edit_text(f"Couldn't download the image: {e}")
        return

    receipt_id = hashlib.sha256(image_bytes).hexdigest()[:16]
    if store.exists(receipt_id):
        await status.edit_text("⚠️ I've already logged this exact photo.")
        return

    try:
        receipt = await extract(image_bytes, _cfg(ctx))
    except ExtractionError as e:
        log.warning("extraction failed: %s", e)
        await status.edit_text("❌ Couldn't read that receipt. Try a clearer, well-lit photo.")
        return

    receipt = categorize(receipt)
    if not receipt.currency or receipt.currency == "USD":
        receipt.currency = client["currency"]  # fall back to client default
    store.save_receipt(receipt_id, uid, receipt)

    kb = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Save", callback_data=f"save:{receipt_id}"),
            InlineKeyboardButton("🗑 Discard", callback_data=f"del:{receipt_id}"),
        ]]
    )
    await status.edit_text(receipt.summary() + "\n\nLog this to your sheet?", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# --- confirm / discard -----------------------------------------------------

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, _, receipt_id = query.data.partition(":")
    store = _store(ctx)
    uid = update.effective_user.id
    client = store.get_client(uid)

    if action == "del":
        store.delete_receipt(receipt_id)
        await query.edit_message_text("\U0001F5D1 Discarded. Send another photo anytime.")
        return

    if action == "save":
        receipt = store.load_receipt(receipt_id)
        if not receipt or not client:
            await query.edit_message_text("⚠️ That receipt expired. Please resend the photo.")
            return
        sheets = _sheets(ctx)
        if sheets is None:
            await query.edit_message_text("✅ Saved locally (Sheets not configured yet).")
            return
        try:
            sheets.append(client["sheet_tab"] or client["name"], receipt_id, receipt)
            store.mark_synced(receipt_id)
            await query.edit_message_text(receipt.summary() + "\n\n✅ Logged to your sheet.", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:  # noqa: BLE001
            log.exception("sheet append failed")
            await query.edit_message_text(
                receipt.summary() + f"\n\n⚠️ Saved locally; sheet sync failed ({e}). Admin can /sync later.",
                parse_mode=ParseMode.MARKDOWN,
            )


# --- admin commands --------------------------------------------------------

async def cmd_adduser(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(ctx, update.effective_user.id):
        return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /adduser <tg_id> <name> [currency]")
        return
    try:
        tg_id = int(args[0])
    except ValueError:
        await update.message.reply_text("tg_id must be a number.")
        return
    rest = args[1:]
    currency = "USD"
    # trailing 3-letter alpha token = currency code (only if a name remains)
    if len(rest) >= 2 and len(rest[-1]) == 3 and rest[-1].isalpha():
        currency = rest[-1].upper()
        rest = rest[:-1]
    name = " ".join(rest)
    _store(ctx).add_client(tg_id, name, currency=currency, sheet_tab=name)
    await update.message.reply_text(f"✅ Added client: {name} (id {tg_id}, {currency}). A '{name}' sheet tab will be created on first save.")


async def cmd_clients(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(ctx, update.effective_user.id):
        return
    rows = _store(ctx).list_clients()
    if not rows:
        await update.message.reply_text("No clients yet. Add one with /adduser.")
        return
    lines = [f"• {r['name']} — id `{r['tg_id']}` ({r['currency']})" for r in rows]
    await update.message.reply_text("*Clients:*\n" + "\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_removeuser(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(ctx, update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /removeuser <tg_id>")
        return
    _store(ctx).deactivate_client(int(ctx.args[0]))
    await update.message.reply_text("✅ Client deactivated.")


async def cmd_sync(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(ctx, update.effective_user.id):
        return
    store, sheets = _store(ctx), _sheets(ctx)
    if sheets is None:
        await update.message.reply_text("Sheets not configured.")
        return
    pending = store.unsynced()
    ok = fail = 0
    for row in pending:
        client = store.get_client(row["tg_id"])
        receipt = store.load_receipt(row["id"])
        if not client or not receipt:
            continue
        try:
            sheets.append(client["sheet_tab"] or client["name"], row["id"], receipt)
            store.mark_synced(row["id"])
            ok += 1
        except Exception:  # noqa: BLE001
            fail += 1
    await update.message.reply_text(f"Sync done: {ok} written, {fail} failed, of {len(pending)} pending.")


# --- wiring ----------------------------------------------------------------

def build_application(cfg: Config, store: Store, sheets: Sheets | None) -> Application:
    app = Application.builder().token(cfg.telegram_token).build()
    app.bot_data.update({"cfg": cfg, "store": store, "sheets": sheets})

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CommandHandler("adduser", cmd_adduser))
    app.add_handler(CommandHandler("clients", cmd_clients))
    app.add_handler(CommandHandler("removeuser", cmd_removeuser))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_photo))
    return app
