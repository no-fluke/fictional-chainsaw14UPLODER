"""
auth.py — MongoDB-based Auth System for MRBERLIN Bot
Commands: /add, /remove, /users, /plan, /setchannel, /settopic, /topics, /removetopic
"""

from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime

from db import db
from vars import OWNER, CREDIT

# ─── AUTH DECORATOR ───────────────────────────────────────────────────────────

def check_auth():
    """
    Decorator: blocks non-authorized users from using a handler.
    Usage:
        @check_auth()
        async def some_handler(client, message): ...
    """
    def decorator(func):
        async def wrapper(client, message, *args, **kwargs):
            bot_info = await client.get_me()
            bot_username = bot_info.username
            if not db.is_user_authorized(message.from_user.id, bot_username):
                await message.reply(
                    "**❌ Access Denied!**\n\n"
                    "<blockquote>You are not authorized to use this bot.\n"
                    "Contact admin to get access or upgrade your plan.</blockquote>\n\n"
                    f"Your ID: `{message.from_user.id}`"
                )
                return
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator


# ─── ADD USER ─────────────────────────────────────────────────────────────────

async def add_user_cmd(client: Client, message: Message):
    """Owner only: /add <user_id> <days>"""
    if message.from_user.id != OWNER:
        await message.reply("❌ Only owner can add users.")
        return

    args = message.text.split()[1:]
    if len(args) != 2:
        await message.reply(
            "❌ **Invalid format!**\n\n"
            "Use: `/add user_id days`\n"
            "Example: `/add 123456789 30`"
        )
        return

    try:
        user_id = int(args[0])
        days = int(args[1])
    except ValueError:
        await message.reply("❌ user_id and days must be numbers.")
        return

    bot_info = await client.get_me()
    bot_username = bot_info.username

    try:
        user = await client.get_users(user_id)
        name = user.first_name
        if user.last_name:
            name += f" {user.last_name}"
    except Exception:
        name = f"User {user_id}"

    success, expiry = db.add_user(user_id, name, days, bot_username)

    if success:
        expiry_str = expiry.strftime("%d-%m-%Y %H:%M:%S")
        await message.reply(
            f"**✅ User Added Successfully!**\n\n"
            f"<blockquote>"
            f"👤 Name: {name}\n"
            f"🆔 User ID: `{user_id}`\n"
            f"📅 Expiry: {expiry_str}\n"
            f"⏳ Days: {days}"
            f"</blockquote>"
        )
        try:
            await client.send_message(
                user_id,
                f"**🎉 Subscription Activated!**\n\n"
                f"<blockquote>Your subscription has been activated.\n"
                f"Expires on: **{expiry_str}**\n\n"
                f"Type /start to begin uploading!</blockquote>"
            )
        except Exception:
            pass
    else:
        await message.reply("❌ Failed to add user. Try again.")


# ─── REMOVE USER ──────────────────────────────────────────────────────────────

async def remove_user_cmd(client: Client, message: Message):
    """Owner only: /remove <user_id>"""
    if message.from_user.id != OWNER:
        await message.reply("❌ Only owner can remove users.")
        return

    args = message.text.split()[1:]
    if len(args) != 1:
        await message.reply("Use: `/remove user_id`")
        return

    try:
        user_id = int(args[0])
    except ValueError:
        await message.reply("❌ Invalid user ID.")
        return

    bot_info = await client.get_me()
    if db.remove_user(user_id, bot_info.username):
        await message.reply(f"✅ User `{user_id}` removed successfully.")
        try:
            await client.send_message(
                user_id,
                "**⚠️ Subscription Ended**\n\n"
                "Your access has been revoked by admin.\n"
                "Contact admin to renew."
            )
        except Exception:
            pass
    else:
        await message.reply(f"❌ User `{user_id}` not found.")


# ─── LIST USERS ───────────────────────────────────────────────────────────────

async def list_users_cmd(client: Client, message: Message):
    """Owner only: /users"""
    if message.from_user.id != OWNER:
        await message.reply("❌ Only owner can view the user list.")
        return

    bot_info = await client.get_me()
    users = db.list_users(bot_info.username)

    if not users:
        await message.reply("📝 No authorized users found.")
        return

    text = "**📝 Authorized Users List**\n\n"
    for u in users:
        expiry = u.get("expiry_date")
        if isinstance(expiry, str):
            expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        days_left = (expiry - datetime.now()).days if expiry else 0
        status = "✅ Active" if days_left > 0 else "❌ Expired"
        text += (
            f"• **{u.get('name', 'Unknown')}**\n"
            f"  ID: `{u['user_id']}`\n"
            f"  Expires: {expiry.strftime('%d-%m-%Y') if expiry else 'N/A'} "
            f"({days_left}d left) {status}\n"
            f"──────────────\n"
        )

    # Split into chunks if too long
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            await message.reply(chunk)
    else:
        await message.reply(text)


# ─── MY PLAN ──────────────────────────────────────────────────────────────────

async def my_plan_cmd(client: Client, message: Message):
    """Any user: /plan — show their subscription details."""
    bot_info = await client.get_me()
    info = db.get_user_expiry_info(message.from_user.id, bot_info.username)

    if message.from_user.id == OWNER:
        await message.reply("**👑 You are the Owner — Unlimited Access!**")
        return

    if not info:
        await message.reply(
            "**❌ No Active Plan**\n\n"
            "<blockquote>You don't have an active subscription.\n"
            f"Contact admin to get access.</blockquote>\n\n"
            f"Your ID: `{message.from_user.id}`"
        )
        return

    status = "✅ Active" if info["is_active"] else "❌ Expired"
    await message.reply(
        f"**📱 Your Plan Details**\n\n"
        f"<blockquote>"
        f"👤 Name: {info['name']}\n"
        f"🆔 ID: `{info['user_id']}`\n"
        f"📅 Expires: {info['expiry_date']}\n"
        f"⏳ Days Left: {info['days_left']}\n"
        f"🔰 Status: {status}"
        f"</blockquote>"
    )


# ─── SET DEFAULT CHANNEL ──────────────────────────────────────────────────────

async def set_channel_cmd(client: Client, message: Message):
    """
    Authorized user: /setchannel <channel_id>
    Saves a default upload channel in MongoDB for this user.
    """
    bot_info = await client.get_me()
    if not db.is_user_authorized(message.from_user.id, bot_info.username):
        await message.reply("❌ You are not authorized.")
        return

    args = message.text.split()[1:]
    if len(args) != 1:
        await message.reply(
            "Use: `/setchannel -100xxxxxxxxxx`\n\n"
            "Send /id in your channel to get the Channel ID."
        )
        return

    try:
        channel_id = int(args[0])
    except ValueError:
        await message.reply("❌ Invalid channel ID. Must be a number.")
        return

    # Verify bot is admin in the channel
    try:
        member = await client.get_chat_member(channel_id, "me")
        if member.status.name not in ("ADMINISTRATOR", "OWNER"):
            await message.reply("❌ I'm not an admin in that channel. Make me admin first.")
            return
    except Exception as e:
        await message.reply(f"❌ Cannot access channel: `{e}`\nMake sure I'm an admin.")
        return

    db.set_user_channel(message.from_user.id, channel_id)
    await message.reply(
        f"✅ **Default channel saved!**\n\n"
        f"<blockquote>Channel ID: `{channel_id}`\n"
        f"All future uploads will go here by default.\n"
        f"You can still change it during upload.</blockquote>"
    )


# ─── SET TOPIC ────────────────────────────────────────────────────────────────

async def set_topic_cmd(client: Client, message: Message):
    """
    Authorized user: /settopic <channel_id> <topic_id> <topic_name>
    Saves a topic mapping for a channel.
    Example: /settopic -1001234567890 5 Physics
    """
    bot_info = await client.get_me()
    if not db.is_user_authorized(message.from_user.id, bot_info.username):
        await message.reply("❌ You are not authorized.")
        return

    args = message.text.split(None, 3)[1:]
    if len(args) < 3:
        await message.reply(
            "Use: `/settopic <channel_id> <topic_id> <topic_name>`\n\n"
            "Example: `/settopic -1001234567890 5 Physics`\n\n"
            "💡 To get topic_id: forward a message from that topic to @getidsbot"
        )
        return

    try:
        channel_id = int(args[0])
        topic_id = int(args[1])
        topic_name = args[2].strip()
    except ValueError:
        await message.reply("❌ channel_id and topic_id must be numbers.")
        return

    db.set_user_topic(message.from_user.id, channel_id, topic_name, topic_id)
    await message.reply(
        f"✅ **Topic saved!**\n\n"
        f"<blockquote>"
        f"📌 Topic Name: `{topic_name}`\n"
        f"🆔 Topic ID: `{topic_id}`\n"
        f"📢 Channel: `{channel_id}`"
        f"</blockquote>\n\n"
        f"During upload, type `yes` to topic-wise upload and use this name."
    )


# ─── LIST TOPICS ──────────────────────────────────────────────────────────────

async def list_topics_cmd(client: Client, message: Message):
    """Authorized user: /topics <channel_id> — list all saved topics."""
    bot_info = await client.get_me()
    if not db.is_user_authorized(message.from_user.id, bot_info.username):
        await message.reply("❌ You are not authorized.")
        return

    args = message.text.split()[1:]

    if not args:
        # Show all saved channels and their topics
        all_data = db.get_all_saved_channels(message.from_user.id)
        if not all_data:
            await message.reply("📭 No topics saved yet.\nUse `/settopic` to save topic mappings.")
            return
        text = "**📋 All Saved Topics**\n\n"
        for ch_id, topics in all_data.items():
            text += f"📢 **Channel:** `{ch_id}`\n"
            for tname, tid in topics.items():
                text += f"  • `{tname}` → ID: `{tid}`\n"
            text += "\n"
        await message.reply(text)
        return

    try:
        channel_id = int(args[0])
    except ValueError:
        await message.reply("❌ Invalid channel ID.")
        return

    topics = db.get_user_topics(message.from_user.id, channel_id)
    if not topics:
        await message.reply(f"📭 No topics saved for channel `{channel_id}`.")
        return

    text = f"**📋 Topics for Channel `{channel_id}`**\n\n"
    for name, tid in topics.items():
        text += f"• `{name}` → ID: `{tid}`\n"
    text += f"\n💡 During upload, type `yes` to use topic-wise upload."
    await message.reply(text)


# ─── REMOVE TOPIC ─────────────────────────────────────────────────────────────

async def remove_topic_cmd(client: Client, message: Message):
    """Authorized user: /removetopic <channel_id> <topic_name>"""
    bot_info = await client.get_me()
    if not db.is_user_authorized(message.from_user.id, bot_info.username):
        await message.reply("❌ You are not authorized.")
        return

    args = message.text.split(None, 2)[1:]
    if len(args) < 2:
        await message.reply("Use: `/removetopic <channel_id> <topic_name>`")
        return

    try:
        channel_id = int(args[0])
        topic_name = args[1].strip()
    except ValueError:
        await message.reply("❌ Invalid channel ID.")
        return

    db.remove_user_topic(message.from_user.id, channel_id, topic_name)
    await message.reply(f"✅ Topic `{topic_name}` removed from channel `{channel_id}`.")


# ─── HANDLER TUPLES (imported and registered in main.py) ─────────────────────

add_user_handler      = (filters.command("add")         & filters.private, add_user_cmd)
remove_user_handler   = (filters.command("remove")      & filters.private, remove_user_cmd)
list_users_handler    = (filters.command("users")       & filters.private, list_users_cmd)
my_plan_handler       = (filters.command("plan")        & filters.private, my_plan_cmd)
set_channel_handler   = (filters.command("setchannel")  & filters.private, set_channel_cmd)
set_topic_handler     = (filters.command("settopic")    & filters.private, set_topic_cmd)
list_topics_handler   = (filters.command("topics")      & filters.private, list_topics_cmd)
remove_topic_handler  = (filters.command("removetopic") & filters.private, remove_topic_cmd)
