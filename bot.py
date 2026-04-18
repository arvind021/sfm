#!/usr/bin/env python3
"""
Pocket FM Extra Episodes Telegram Bot
Features:
- Force Channel Join
- All Stories with Episodes (Audio)
- Paytm / PhonePe Manual Payment + Screenshot Verification
- Custom Subscription Plans (Admin manages)
- Premium Episodes (locked for non-subscribers)
- Full Admin Panel
"""

import os, json, logging, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)
from telegram.error import TelegramError

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
DATA_FILE   = "data.json"

# ─────────────────────────────────────────────
#  FILE HELPERS
# ─────────────────────────────────────────────
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"stories": {}, "subscriptions": {}, "plans": {}, "pending_payments": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    for k in ("stories", "subscriptions", "plans", "pending_payments"):
        d.setdefault(k, {})
    return d

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
#  CONVERSATION STATES
# ─────────────────────────────────────────────
(
    ADMIN_MENU,
    ADD_STORY_NAME,
    ADD_EP_STORY, ADD_EP_NUMBER, ADD_EP_TITLE, ADD_EP_FILE,
    DEL_EP_STORY, DEL_EP_NUMBER,
    EDIT_CONFIG_VAL,
    ADD_PLAN_NAME, ADD_PLAN_PRICE, ADD_PLAN_DAYS, ADD_PLAN_DESC,
    DEL_PLAN_KEY,
    PAY_SCREENSHOT,
) = range(15)

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
async def is_member(bot, user_id: int, channel: str) -> bool:
    try:
        member = await bot.get_chat_member(channel, user_id)
        return member.status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except TelegramError:
        return False

def admin_check(user_id: int, config: dict) -> bool:
    return user_id in config.get("admin_ids", [])

def is_subscribed(user_id: int, data: dict) -> bool:
    sub = data["subscriptions"].get(str(user_id))
    if not sub: return False
    return datetime.datetime.fromisoformat(sub["expiry"]) > datetime.datetime.now()

def sub_info(user_id: int, data: dict) -> str:
    sub = data["subscriptions"].get(str(user_id))
    if not sub: return ""
    expiry = datetime.datetime.fromisoformat(sub["expiry"])
    remaining = (expiry - datetime.datetime.now()).days
    if remaining >= 0:
        return f"\n✅ *{sub['plan_name']}* active — {expiry.strftime('%d %b %Y')} tak ({remaining} days left)\n"
    return "\n⚠️ Subscription expired!\n"

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 All Story",    callback_data="all_story")],
        [InlineKeyboardButton("💎 Subscription", callback_data="subscription")],
        [InlineKeyboardButton("🎧 Support",      callback_data="support"),
         InlineKeyboardButton("📢 Channel",      callback_data="channel")],
    ])

# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    config  = load_config()
    user    = update.effective_user
    channel = config["force_channel"]
    if not await is_member(ctx.bot, user.id, channel):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Join Channel", url=f"https://t.me/{channel.lstrip('@')}")],
            [InlineKeyboardButton("🔄 Check Again",  callback_data="check_join")]
        ])
        await update.message.reply_text(
            f"👋 *Namaste {user.first_name}!*\n\n"
            "🔒 Bot use karne ke liye pehle hamara channel join karo:\n\n"
            f"➡️ {channel}",
            parse_mode="Markdown", reply_markup=kb)
        return
    await send_welcome(update, ctx)

async def send_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    data   = load_data()
    user   = update.effective_user if update.message else update.callback_query.from_user

    # ── SUBSCRIPTION WALL ────────────────────
    # Admins bypass the wall
    if not admin_check(user.id, config) and not is_subscribed(user.id, data):
        text = (
            f"🔒 *Pocket FM Extra Episodes*\n\n"
            f"Namaste {user.first_name}! 👋\n\n"
            "⚠️ *Ye bot sirf subscribers ke liye hai!*\n\n"
            "💎 Subscription lo aur saare exclusive episodes enjoy karo:\n"
            "🎧 Unlimited episodes\n"
            "📱 Har device pe access\n"
            "🔄 New episodes turant milenge\n\n"
            "Neeche subscribe karo 👇"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Subscribe Now",  callback_data="subscription")],
            [InlineKeyboardButton("🎧 Support",        callback_data="support"),
             InlineKeyboardButton("📢 Channel",        callback_data="channel")],
        ])
        if update.message:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    # ── SUBSCRIBED / ADMIN ───────────────────
    text = (
        f"🎙️ *Pocket FM Extra Episodes*\n\n"
        f"Welcome {user.first_name}! 🎉"
        f"{sub_info(user.id, data)}\n"
        "Exclusive episodes yahan milenge.\n"
        "Neeche buttons se choose karo 👇"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ─────────────────────────────────────────────
#  MAIN BUTTON HANDLER
# ─────────────────────────────────────────────
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query
    config = load_config()
    data   = load_data()
    user   = q.from_user
    await q.answer()

    if q.data == "check_join":
        if await is_member(ctx.bot, user.id, config["force_channel"]):
            await send_welcome(update, ctx)
        else:
            await q.answer("❌ Abhi join nahi kiya!", show_alert=True)
        return

    if q.data == "back_home":
        await send_welcome(update, ctx); return

    # ── GLOBAL SUBSCRIPTION GATE ─────────────
    open_buttons = ("subscription", "support", "channel", "buyplan_", "send_ss_")
    is_open = any(q.data == b or q.data.startswith(b) for b in open_buttons)
    if not is_open and not admin_check(user.id, config) and not is_subscribed(user.id, data):
        await q.answer("🔒 Subscription chahiye!", show_alert=True)
        await q.edit_message_text(
            "🔒 *Access Denied!*\n\n"
            "Ye feature sirf subscribers ke liye hai.\n\n"
            "💎 Subscription lo aur poora bot unlock karo!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Subscribe Now", callback_data="subscription")],
                [InlineKeyboardButton("🔙 Back",          callback_data="back_home")],
            ]))
        return

    # ── all story ────────────────────────────
    if q.data == "all_story":
        stories = data.get("stories", {})
        if not stories:
            await q.edit_message_text("📭 Koi story available nahi hai abhi.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]))
            return
        kb = [[InlineKeyboardButton(f"📖 {v['name']}", callback_data=f"story_{k}")]
              for k, v in stories.items()]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_home")])
        await q.edit_message_text("📚 *Sabhi Stories:*\nEk story select karo 👇",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ── single story ─────────────────────────
    if q.data.startswith("story_"):
        story_key = q.data[6:]
        story     = data["stories"].get(story_key)
        if not story:
            await q.answer("Story nahi mili!", show_alert=True); return
        episodes = story.get("episodes", {})
        ep_nums  = sorted(episodes.keys(), key=lambda x: int(x))
        kb, row  = [], []
        for ep_num in ep_nums:
            row.append(InlineKeyboardButton(f"Ep {ep_num}", callback_data=f"ep_{story_key}_{ep_num}"))
            if len(row) == 5: kb.append(row); row = []
        if row: kb.append(row)
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="all_story")])
        await q.edit_message_text(
            f"🎙️ *{story['name']}*\n\n📌 Total Episodes: *{len(episodes)}*\n\nEpisode number select karo 👇",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ── single episode ────────────────────────
    if q.data.startswith("ep_"):
        parts     = q.data.split("_", 2)
        story_key = parts[1]; ep_num = parts[2]
        story     = data["stories"].get(story_key)
        episode   = story["episodes"].get(ep_num) if story else None
        if not episode:
            await q.answer("Episode nahi mila!", show_alert=True); return

        file_id = episode.get("file_id")
        if file_id:
            await ctx.bot.send_audio(chat_id=user.id, audio=file_id,
                caption=f"🎧 *{story['name']}*\n📌 Episode {ep_num}: _{episode['title']}_",
                parse_mode="Markdown")
            await q.answer("✅ Episode bheja ja raha hai!")
        else:
            await q.answer("⚠️ Audio file abhi available nahi.", show_alert=True)
        return

    # ── subscription ─────────────────────────
    if q.data == "subscription":
        if is_subscribed(user.id, data):
            await q.edit_message_text(
                f"✅ *Aapka Subscription Active Hai!*\n\n"
                f"📋 {sub_info(user.id, data).strip()}\n\nEnjoy karo saare episodes! 🎧",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]))
            return
        plans = data.get("plans", {})
        if not plans:
            await q.edit_message_text("⚠️ Abhi koi plan available nahi. Baad mein try karo.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]))
            return
        text = "💎 *Subscription Plans*\n\nEk plan choose karo:\n\n"
        kb   = []
        for key, plan in plans.items():
            text += f"*{plan['name']}* — ₹{plan['price']} / {plan['days']} din\n_{plan.get('desc','')}_\n\n"
            kb.append([InlineKeyboardButton(f"{plan['name']} — ₹{plan['price']}", callback_data=f"buyplan_{key}")])
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_home")])
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ── buy plan → payment details ────────────
    if q.data.startswith("buyplan_"):
        plan_key = q.data[8:]
        plan     = data["plans"].get(plan_key)
        if not plan:
            await q.answer("Plan nahi mila!", show_alert=True); return
        upi_id   = config.get("upi_id", "yourname@paytm")
        upi_name = config.get("upi_name", "Pocket FM")
        text = (
            f"💳 *Payment Details*\n\n"
            f"📦 Plan: *{plan['name']}*\n"
            f"💰 Amount: *₹{plan['price']}*\n"
            f"📅 Duration: *{plan['days']} din*\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📱 *UPI ID:* `{upi_id}`\n"
            f"👤 *Name:* {upi_name}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"*Steps:*\n"
            f"1️⃣ Paytm / PhonePe se ₹{plan['price']} bhejo\n"
            f"2️⃣ Payment screenshot lo\n"
            f"3️⃣ Neeche button dabao aur screenshot bhejo\n\n"
            f"⏱️ Verification: 5–30 minutes"
        )
        ctx.user_data["pay_plan"] = plan_key
        await q.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Screenshot Bhejo", callback_data=f"send_ss_{plan_key}")],
                [InlineKeyboardButton("🔙 Back",             callback_data="subscription")]
            ]))
        return

    # ── support ──────────────────────────────
    if q.data == "support":
        await q.edit_message_text(
            "🎧 *Support*\n\n" + config.get("support_text", "Koi problem ho to contact karo 👇"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact Support", url=config.get("support_link","https://t.me"))],
                [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
            ]))
        return

    # ── channel ──────────────────────────────
    if q.data == "channel":
        await q.edit_message_text("📢 *Our Channel*\n\nLatest updates ke liye join karo!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel",
                    url=f"https://t.me/{config['force_channel'].lstrip('@')}")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
            ]))
        return

# ─────────────────────────────────────────────
#  PAYMENT CONV HANDLER
# ─────────────────────────────────────────────
async def pay_screenshot_trigger(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q        = update.callback_query
    plan_key = q.data[8:]   # send_ss_<key>
    ctx.user_data["pay_plan"] = plan_key
    await q.answer()
    await q.edit_message_text(
        "📸 *Payment Screenshot Bhejo*\n\n"
        "Is chat mein apna payment screenshot bhejo.\n"
        "Admin verify karenge aur subscription activate ho jayegi! ✅",
        parse_mode="Markdown")
    return PAY_SCREENSHOT

async def pay_screenshot_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg      = update.message
    plan_key = ctx.user_data.get("pay_plan")
    data     = load_data()
    config   = load_config()
    user     = msg.from_user

    if not msg.photo and not msg.document:
        await msg.reply_text("❌ Screenshot (image) bhejo!"); return PAY_SCREENSHOT

    plan = data["plans"].get(plan_key)
    if not plan:
        await msg.reply_text("❌ Plan nahi mila. /start se dobara try karo.")
        return ConversationHandler.END

    file_id  = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    pend_key = f"{user.id}_{plan_key}"
    data["pending_payments"][pend_key] = {
        "user_id": user.id, "username": user.username or "N/A",
        "first_name": user.first_name, "plan_key": plan_key,
        "plan_name": plan["name"], "amount": plan["price"],
        "file_id": file_id, "timestamp": datetime.datetime.now().isoformat()
    }
    save_data(data)

    await msg.reply_text(
        f"✅ *Screenshot Received!*\n\n"
        f"📦 Plan: {plan['name']}\n💰 Amount: ₹{plan['price']}\n\n"
        "Admin jaldi verify karenge.\n⏱️ 5–30 min mein subscription activate ho jayegi! 🎉",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Home", callback_data="back_home")]]))

    # Notify admins
    for admin_id in config.get("admin_ids", []):
        try:
            await ctx.bot.send_photo(
                chat_id=admin_id, photo=file_id,
                caption=(
                    f"💳 *New Payment Request!*\n\n"
                    f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                    f"🆔 ID: `{user.id}`\n"
                    f"📦 Plan: {plan['name']}\n💰 ₹{plan['price']}\n\n"
                    f"Approve: `/approve {user.id} {plan_key}`"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Approve", callback_data=f"adm_approve_{user.id}_{plan_key}")],
                    [InlineKeyboardButton("❌ Reject",  callback_data=f"adm_reject_{user.id}_{plan_key}")]
                ]))
        except Exception: pass

    return ConversationHandler.END

# ─────────────────────────────────────────────
#  ADMIN APPROVE / REJECT
# ─────────────────────────────────────────────
async def admin_approve_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query
    config = load_config()
    data   = load_data()
    await q.answer()
    if not admin_check(q.from_user.id, config):
        await q.answer("❌ Admin only!", show_alert=True); return

    if q.data.startswith("adm_approve_"):
        rest      = q.data[12:]
        parts     = rest.split("_", 1)
        user_id   = int(parts[0]); plan_key = parts[1]
        plan      = data["plans"].get(plan_key)
        if not plan: await q.answer("Plan nahi mila!", show_alert=True); return

        expiry = datetime.datetime.now() + datetime.timedelta(days=int(plan["days"]))
        data["subscriptions"][str(user_id)] = {
            "plan_key": plan_key, "plan_name": plan["name"],
            "expiry": expiry.isoformat(), "activated": datetime.datetime.now().isoformat()
        }
        data["pending_payments"].pop(f"{user_id}_{plan_key}", None)
        save_data(data)

        await q.edit_message_caption(
            caption=(q.message.caption or "") + f"\n\n✅ APPROVED by @{q.from_user.username}",
            parse_mode="Markdown")
        try:
            await ctx.bot.send_message(chat_id=user_id,
                text=(f"🎉 *Subscription Activated!*\n\n"
                      f"📦 Plan: *{plan['name']}*\n"
                      f"📅 Valid till: *{expiry.strftime('%d %b %Y')}*\n\n"
                      "Ab saare premium episodes enjoy karo! 🎧"),
                parse_mode="Markdown", reply_markup=main_keyboard())
        except Exception: pass

    elif q.data.startswith("adm_reject_"):
        rest    = q.data[11:]
        parts   = rest.split("_", 1)
        user_id = int(parts[0]); plan_key = parts[1]
        data["pending_payments"].pop(f"{user_id}_{plan_key}", None)
        save_data(data)
        await q.edit_message_caption(
            caption=(q.message.caption or "") + f"\n\n❌ REJECTED by @{q.from_user.username}",
            parse_mode="Markdown")
        try:
            await ctx.bot.send_message(chat_id=user_id,
                text=("❌ *Payment Rejected*\n\nPayment verify nahi ho saka.\n"
                      "Sahi screenshot bhejo ya support se contact karo."),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Support", callback_data="support")],
                    [InlineKeyboardButton("🔄 Try Again", callback_data="subscription")]
                ]))
        except Exception: pass

# ─────────────────────────────────────────────
#  /approve command (manual)
# ─────────────────────────────────────────────
async def approve_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not admin_check(update.effective_user.id, config):
        await update.message.reply_text("❌ Admin only!"); return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/approve <user_id> <plan_key>`", parse_mode="Markdown"); return
    user_id = int(args[0]); plan_key = args[1]
    data    = load_data(); plan = data["plans"].get(plan_key)
    if not plan:
        await update.message.reply_text(f"❌ Plan `{plan_key}` nahi mila!", parse_mode="Markdown"); return
    expiry = datetime.datetime.now() + datetime.timedelta(days=int(plan["days"]))
    data["subscriptions"][str(user_id)] = {
        "plan_key": plan_key, "plan_name": plan["name"],
        "expiry": expiry.isoformat(), "activated": datetime.datetime.now().isoformat()
    }
    save_data(data)
    await update.message.reply_text(
        f"✅ User `{user_id}` ko *{plan['name']}* diya!\n📅 Expiry: {expiry.strftime('%d %b %Y')}",
        parse_mode="Markdown")
    try:
        await ctx.bot.send_message(chat_id=user_id,
            text=(f"🎉 *Subscription Activated!*\n\n"
                  f"📦 Plan: *{plan['name']}*\n📅 Valid till: *{expiry.strftime('%d %b %Y')}*\n\n"
                  "Ab saare premium episodes enjoy karo! 🎧"),
            parse_mode="Markdown", reply_markup=main_keyboard())
    except Exception: pass

# ─────────────────────────────────────────────
#  /setpremium command
# ─────────────────────────────────────────────
async def set_premium_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not admin_check(update.effective_user.id, config):
        await update.message.reply_text("❌ Admin only!"); return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/setpremium <story_key> <ep_num>`", parse_mode="Markdown"); return
    story_key, ep_num = args[0], args[1]
    data  = load_data(); story = data["stories"].get(story_key)
    if not story or ep_num not in story.get("episodes", {}):
        await update.message.reply_text("❌ Story ya episode nahi mila!"); return
    story["episodes"][ep_num]["premium"] = True; save_data(data)
    await update.message.reply_text(
        f"✅ Episode {ep_num} of *{story['name']}* ab Premium hai 🔒", parse_mode="Markdown")

# ─────────────────────────────────────────────
#  ADMIN PANEL
# ─────────────────────────────────────────────
def admin_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Story",    callback_data="adm_add_story"),
         InlineKeyboardButton("📋 List Stories", callback_data="adm_list_stories")],
        [InlineKeyboardButton("🎵 Add Episode",  callback_data="adm_add_ep"),
         InlineKeyboardButton("🗑️ Del Episode",  callback_data="adm_del_ep")],
        [InlineKeyboardButton("💎 Plans",        callback_data="adm_plans"),
         InlineKeyboardButton("📊 Pending Pay",  callback_data="adm_pending")],
        [InlineKeyboardButton("👥 Active Subs",  callback_data="adm_subs"),
         InlineKeyboardButton("⚙️ Settings",     callback_data="adm_settings")],
        [InlineKeyboardButton("❌ Close",         callback_data="adm_close")],
    ])

async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not admin_check(update.effective_user.id, config):
        await update.message.reply_text("❌ You are not an admin!"); return ADMIN_MENU
    await update.message.reply_text("🔐 *Admin Panel*\n\nKya karna chahte ho?",
        parse_mode="Markdown", reply_markup=admin_main_kb())
    return ADMIN_MENU

async def admin_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query
    config = load_config()
    data   = load_data()
    await q.answer()

    # list stories
    if q.data == "adm_list_stories":
        stories = data.get("stories", {})
        txt = "📚 *Stories:*\n\n" + ("".join(
            f"• `{k}` — {v['name']} ({len(v.get('episodes',{}))} eps)\n"
            for k,v in stories.items()) or "Koi story nahi.\n")
        await q.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]]))
        return ADMIN_MENU

    # add story
    if q.data == "adm_add_story":
        await q.edit_message_text("📖 Naye story ka naam likho:"); return ADD_STORY_NAME

    # add episode
    if q.data == "adm_add_ep":
        stories = data.get("stories", {})
        if not stories:
            await q.edit_message_text("❌ Pehle ek story add karo.\n\n/admin"); return ADMIN_MENU
        kb = [[InlineKeyboardButton(v["name"], callback_data=f"adm_ep_story_{k}")]
              for k,v in stories.items()]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="adm_back")])
        await q.edit_message_text("🎵 Kis story mein episode add karna hai?",
            reply_markup=InlineKeyboardMarkup(kb)); return ADD_EP_STORY

    # del episode
    if q.data == "adm_del_ep":
        stories = data.get("stories", {})
        if not stories:
            await q.edit_message_text("❌ Koi story nahi hai.\n\n/admin"); return ADMIN_MENU
        kb = [[InlineKeyboardButton(v["name"], callback_data=f"adm_del_story_{k}")]
              for k,v in stories.items()]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="adm_back")])
        await q.edit_message_text("🗑️ Kis story se episode delete karna hai?",
            reply_markup=InlineKeyboardMarkup(kb)); return DEL_EP_STORY

    if q.data.startswith("adm_del_story_"):
        ctx.user_data["del_story_key"] = q.data[14:]
        await q.edit_message_text("🗑️ Episode number likho jo delete karna hai:"); return DEL_EP_NUMBER

    if q.data.startswith("adm_ep_story_"):
        ctx.user_data["new_ep_story"] = q.data[13:]
        await q.edit_message_text("🔢 Episode number likho (e.g. 1, 2, 3):"); return ADD_EP_NUMBER

    # plans
    if q.data == "adm_plans":
        plans = data.get("plans", {})
        txt = "💎 *Plans:*\n\n" + ("".join(
            f"• `{k}` — {v['name']} | ₹{v['price']} | {v['days']} din\n"
            for k,v in plans.items()) or "Koi plan nahi.\n")
        await q.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Plan", callback_data="adm_add_plan"),
                 InlineKeyboardButton("🗑️ Del Plan", callback_data="adm_del_plan")],
                [InlineKeyboardButton("🔙 Back",     callback_data="adm_back")]
            ])); return ADMIN_MENU

    if q.data == "adm_add_plan":
        await q.edit_message_text("📝 Plan ka naam likho (e.g. Monthly):"); return ADD_PLAN_NAME

    if q.data == "adm_del_plan":
        plans = data.get("plans", {})
        if not plans:
            await q.edit_message_text("❌ Koi plan nahi.\n\n/admin"); return ADMIN_MENU
        kb = [[InlineKeyboardButton(f"{v['name']} (₹{v['price']})", callback_data=f"adm_delplan_{k}")]
              for k,v in plans.items()]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="adm_plans")])
        await q.edit_message_text("🗑️ Kaunsa plan delete karna hai?",
            reply_markup=InlineKeyboardMarkup(kb)); return DEL_PLAN_KEY

    if q.data.startswith("adm_delplan_"):
        plan_key = q.data[12:]
        data["plans"].pop(plan_key, None); save_data(data)
        await q.edit_message_text(f"✅ Plan `{plan_key}` delete ho gaya!\n\n/admin",
            parse_mode="Markdown"); return ADMIN_MENU

    # pending payments
    if q.data == "adm_pending":
        pending = data.get("pending_payments", {})
        if not pending:
            await q.edit_message_text("✅ Koi pending payment nahi hai!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])); return ADMIN_MENU
        txt = "⏳ *Pending Payments:*\n\n"
        for p in pending.values():
            txt += f"👤 {p['first_name']} (@{p['username']}) | 🆔 `{p['user_id']}`\n📦 {p['plan_name']} | ₹{p['amount']}\n\n"
        txt += "Approve: `/approve <user_id> <plan_key>`"
        await q.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])); return ADMIN_MENU

    # active subscriptions
    if q.data == "adm_subs":
        subs = data.get("subscriptions", {})
        now  = datetime.datetime.now()
        active = [(uid, s) for uid, s in subs.items()
                  if datetime.datetime.fromisoformat(s["expiry"]) > now]
        txt = f"👥 *Active Subscriptions: {len(active)}*\n\n"
        for uid, s in active:
            expiry = datetime.datetime.fromisoformat(s["expiry"])
            txt += f"🆔 `{uid}` — {s['plan_name']} | {expiry.strftime('%d %b %Y')}\n"
        await q.edit_message_text(txt or "Koi active sub nahi.", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])); return ADMIN_MENU

    # settings
    if q.data == "adm_settings":
        await q.edit_message_text("⚙️ *Settings*\n\nKya change karna hai?", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Force Channel", callback_data="adm_set_force_channel")],
                [InlineKeyboardButton("📱 UPI ID",        callback_data="adm_set_upi_id"),
                 InlineKeyboardButton("👤 UPI Name",      callback_data="adm_set_upi_name")],
                [InlineKeyboardButton("💬 Support Link",  callback_data="adm_set_support_link")],
                [InlineKeyboardButton("🔙 Back",          callback_data="adm_back")],
            ])); return ADMIN_MENU

    if q.data.startswith("adm_set_"):
        ctx.user_data["edit_config_key"] = q.data[8:]
        await q.edit_message_text(f"✏️ `{q.data[8:]}` ki nayi value likho:", parse_mode="Markdown")
        return EDIT_CONFIG_VAL

    if q.data in ("adm_back", "adm_close"):
        await q.edit_message_text("🔐 *Admin Panel*\n\nKya karna chahte ho?",
            parse_mode="Markdown", reply_markup=admin_main_kb()); return ADMIN_MENU

    return ADMIN_MENU

# ─────────────────────────────────────────────
#  CONV STATE HANDLERS
# ─────────────────────────────────────────────
async def add_story_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    key  = name.lower().replace(" ", "_")[:20]
    data = load_data(); data["stories"][key] = {"name": name, "episodes": {}}; save_data(data)
    await update.message.reply_text(f"✅ Story *{name}* add ho gayi!\n`Key: {key}`\n\n/admin", parse_mode="Markdown")
    return ADMIN_MENU

async def add_ep_number(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: num = str(int(update.message.text.strip()))
    except ValueError:
        await update.message.reply_text("❌ Sirf number likho!"); return ADD_EP_NUMBER
    ctx.user_data["new_ep_num"] = num
    await update.message.reply_text("📝 Episode ka title likho:"); return ADD_EP_TITLE

async def add_ep_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_ep_title"] = update.message.text.strip()
    await update.message.reply_text("🎵 Audio file bhejo:"); return ADD_EP_FILE

async def add_ep_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    file_id = None
    if msg.audio: file_id = msg.audio.file_id
    elif msg.voice: file_id = msg.voice.file_id
    elif msg.document: file_id = msg.document.file_id
    if not file_id:
        await msg.reply_text("❌ Audio file bhejo!"); return ADD_EP_FILE
    story_key = ctx.user_data["new_ep_story"]; ep_num = ctx.user_data["new_ep_num"]
    ep_title  = ctx.user_data["new_ep_title"]
    data  = load_data(); story = data["stories"].get(story_key)
    if not story:
        await msg.reply_text("❌ Story nahi mili!"); return ADMIN_MENU
    story["episodes"][ep_num] = {"title": ep_title, "file_id": file_id, "premium": False}
    save_data(data)
    await msg.reply_text(
        f"✅ *Episode {ep_num}* add ho gaya!\nStory: {story['name']}\nTitle: {ep_title}\n\n"
        f"Premium banane ke liye: `/setpremium {story_key} {ep_num}`\n\n/admin",
        parse_mode="Markdown"); return ADMIN_MENU

async def del_ep_number(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: num = str(int(update.message.text.strip()))
    except ValueError:
        await update.message.reply_text("❌ Sirf number likho!"); return DEL_EP_NUMBER
    story_key = ctx.user_data["del_story_key"]
    data = load_data(); story = data["stories"].get(story_key)
    if story and num in story.get("episodes", {}):
        del story["episodes"][num]; save_data(data)
        await update.message.reply_text(f"✅ Episode {num} delete ho gaya!\n\n/admin")
    else:
        await update.message.reply_text(f"❌ Episode {num} nahi mila!\n\n/admin")
    return ADMIN_MENU

async def edit_config_val(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    key = ctx.user_data["edit_config_key"]; value = update.message.text.strip()
    config = load_config(); config[key] = value
    with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(config, f, ensure_ascii=False, indent=2)
    await update.message.reply_text(f"✅ `{key}` = `{value}`\n\n/admin", parse_mode="Markdown")
    return ADMIN_MENU

async def add_plan_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_plan_name"] = update.message.text.strip()
    await update.message.reply_text("💰 Price likho (e.g. 99):"); return ADD_PLAN_PRICE

async def add_plan_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: price = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Sirf number likho!"); return ADD_PLAN_PRICE
    ctx.user_data["new_plan_price"] = price
    await update.message.reply_text("📅 Kitne din? (e.g. 30):"); return ADD_PLAN_DAYS

async def add_plan_days(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: days = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Sirf number likho!"); return ADD_PLAN_DAYS
    ctx.user_data["new_plan_days"] = days
    await update.message.reply_text("📝 Short description likho:"); return ADD_PLAN_DESC

async def add_plan_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    name = ctx.user_data["new_plan_name"]; price = ctx.user_data["new_plan_price"]; days = ctx.user_data["new_plan_days"]
    plan_key = name.lower().replace(" ", "_")[:15]
    data = load_data(); data["plans"][plan_key] = {"name": name, "price": price, "days": days, "desc": desc}; save_data(data)
    await update.message.reply_text(
        f"✅ *Plan Added!*\n📦 {name} | ₹{price} | {days} din\n`Key: {plan_key}`\n\n/admin",
        parse_mode="Markdown"); return ADMIN_MENU

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.\n\n/admin"); return ConversationHandler.END

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    config = load_config()
    app    = Application.builder().token(config["bot_token"]).build()

    # User
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler,
        pattern="^(all_story|subscription|support|channel|back_home|check_join|story_|ep_|buyplan_)"))

    # Payment screenshot conv
    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pay_screenshot_trigger, pattern="^send_ss_")],
        states={PAY_SCREENSHOT: [MessageHandler(filters.PHOTO | filters.Document.ALL, pay_screenshot_received)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False, allow_reentry=True,
    )
    app.add_handler(pay_conv)

    # Admin approve/reject (outside conv, for photo captions)
    app.add_handler(CallbackQueryHandler(admin_approve_reject, pattern="^adm_(approve|reject)_"))

    # Admin commands
    app.add_handler(CommandHandler("approve",    approve_cmd))
    app.add_handler(CommandHandler("setpremium", set_premium_cmd))

    # Admin panel conv
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_cmd)],
        states={
            ADMIN_MENU:      [CallbackQueryHandler(admin_button)],
            ADD_STORY_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_story_name)],
            ADD_EP_STORY:    [CallbackQueryHandler(admin_button)],
            ADD_EP_NUMBER:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ep_number)],
            ADD_EP_TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ep_title)],
            ADD_EP_FILE:     [MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.ALL, add_ep_file)],
            DEL_EP_STORY:    [CallbackQueryHandler(admin_button)],
            DEL_EP_NUMBER:   [MessageHandler(filters.TEXT & ~filters.COMMAND, del_ep_number)],
            EDIT_CONFIG_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_config_val)],
            ADD_PLAN_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plan_name)],
            ADD_PLAN_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plan_price)],
            ADD_PLAN_DAYS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plan_days)],
            ADD_PLAN_DESC:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plan_desc)],
            DEL_PLAN_KEY:    [CallbackQueryHandler(admin_button)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False, allow_reentry=True,
    )
    app.add_handler(admin_conv)

    logger.info("✅ Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
