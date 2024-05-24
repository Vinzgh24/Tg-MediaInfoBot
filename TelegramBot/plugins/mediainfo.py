import re
import os
import time
import json
import httpx
import asyncio
import requests
import subprocess
from html import escape
from async_timeout import timeout 
from urllib.parse import unquote

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from TelegramBot.helpers.functions import *
from TelegramBot.logging import LOGGER
from TelegramBot.helpers.filters import check_auth
from TelegramBot.helpers.mediainfo_paste import mediainfo_paste
from TelegramBot.helpers.gdrivehelper import GoogleDriveHelper

async def gdrive_mediainfo(message, url, isRaw):
    """
    Generates Mediainfo from a Google Drive file.
    """

    reply_msg = await message.reply_text(
        "Generating Mediainfo, Please wait...", quote=True)
    try:
        GD = GoogleDriveHelper()
        metadata = GD.get_metadata(url)
        file_id = GD.get_id(url)

        rand_str = randstr()
        download_path = f"download/{rand_str}_{file_id}"

        service = build(
            "drive", "v3", cache_discovery=False, credentials=GD.get_credentials())
        request = service.files().get_media(fileId=file_id)

        with open(download_path, "wb") as file:
            downloader = MediaIoBaseDownload(file, request)
            downloader.next_chunk()

        mediainfo = await async_subprocess(f"mediainfo {download_path}")
        mediainfo_json = await async_subprocess(f"mediainfo {download_path} --Output=JSON")
        mediainfo_json = json.loads(mediainfo_json)

        filesize = get_readable_bytes(float(metadata["size"]))
        
        filename = metadata["name"]

        lines = mediainfo.splitlines()
        for i in range(len(lines)):
            if "Complete name" in lines[i]:
                lines[i] = re.sub(r": .+", ": " + filename, lines[i])

            elif "File size" in lines[i]:
                lines[i] = re.sub(r": .+", ": " + filesize, lines[i])

            elif (
                "Overall bit rate" in lines[i]
                and "Overall bit rate mode" not in lines[i]
            ):
                duration = float(mediainfo_json["media"]["track"][0]["Duration"])
                bitrate = get_readable_bitrate(
                    float(metadata["size"]) * 8 / (duration * 1000))
                lines[i] = re.sub(r": .+", ": " + bitrate, lines[i])

            elif "IsTruncated" in lines[i] or "FileExtension_Invalid" in lines[i]:
                lines[i] = ""

        remove_N(lines)
        with open(f"{download_path}.txt", "w") as f:
            f.write("\n".join(lines))

        if isRaw:
            await message.reply_document(
                f"{download_path}.txt", caption=f"**File Name :** `{filename}`")
            os.remove(f"{download_path}.txt")
            os.remove(f"{download_path}")
            return await reply_msg.delete()

        with open(f"{download_path}.txt", "r+") as file:
            content = file.read()

        output = mediainfo_paste(text=content, title=filename)
        button = InlineKeyboardMarkup([
        [InlineKeyboardButton("View Mediainfo", url=output)]
    ])
        
        msg = f"<blockquote><code>{filename}</code></blockquote> \n**Size :** <code>{filesize}</code>"
        
        await reply_msg.edit(
            text=msg,
            reply_markup=button,
            disable_web_page_preview=False
        )
        os.remove(f"{download_path}.txt")
        os.remove(download_path)

    except Exception as error:
        LOGGER(__name__).error(error)        
        return await reply_msg.edit(
            "Something went wrong while processing Gdrive link.\n\n (Make sure that the gdrive link is not rate limited, is public link and not a folder)")
        
async def async_subprocess(shell_command):
    process = await asyncio.create_subprocess_shell(
        shell_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"Command failed: {stderr.decode()}")
    return stdout.decode()

async def ddl_mediainfo(message, url, isRaw):
    """
    Generates Mediainfo from a Direct Download Link.
    """

    reply_msg = await message.reply_text(
        "Generating Mediainfo, Please wait...", quote=True)
    try:
        filename = re.search(".+/(.+)", url).group(1)
        if len(filename) > 60:
            filename = filename[-60:]

        rand_str = randstr()
        download_path = f"download/{rand_str}_{filename}"
        
        # Create the download directory if it doesn't exist
        os.makedirs(os.path.dirname(download_path), exist_ok=True)
        
        # Use aria2c to download the file
        aria2c_command = f"aria2c --dir=\"{os.path.dirname(download_path)}\" --out=\"{os.path.basename(download_path)}\" \"{url}\""
        await async_subprocess(aria2c_command)
          
        mediainfo = await async_subprocess(f"mediainfo {download_path}")
        mediainfo_json = await async_subprocess(
            f"mediainfo {download_path} --Output=JSON")
        mediainfo_json = json.loads(mediainfo_json)
        
        filesize = requests.head(url).headers.get("content-length")
        lines = mediainfo.splitlines()
        for i in range(len(lines)):
            if "Complete name" in lines[i]:
                lines[i] = re.sub(r": .+", ": " + unquote(filename), lines[i])

            elif "File size" in lines[i]:
                lines[i] = re.sub(
                    r": .+", ": " + get_readable_bytes(float(filesize)), lines[i])

            elif (
                "Overall bit rate" in lines[i]
                and "Overall bit rate mode" not in lines[i]
            ):
                duration = float(mediainfo_json["media"]["track"][0]["Duration"])
                bitrate = get_readable_bitrate(float(filesize) * 8 / (duration * 1000))
                lines[i] = re.sub(r": .+", ": " + bitrate, lines[i])

            elif "IsTruncated" in lines[i] or "FileExtension_Invalid" in lines[i]:
                lines[i] = ""

        with open(f"{download_path}.txt", "w") as f:
            f.write("\n".join(lines))

        if isRaw:
            await message.reply_document(
                f"{download_path}.txt", caption=f"**File Name :** `{filename}`")
            os.remove(f"{download_path}.txt")
            os.remove(f"{download_path}")
            return await reply_msg.delete()

        with open(f"{download_path}.txt", "r+") as file:
            content = file.read()

        output = mediainfo_paste(text=content, title=filename)
        await reply_msg.edit(
            f"**File Name :** `{unquote(filename)}`\n\n**Mediainfo :** {output}",
            disable_web_page_preview=False)

        os.remove(f"{download_path}.txt")
        os.remove(f"{download_path}")

    except asyncio.TimeoutError:
        return await reply_msg.edit(
            "Sorry! process failed due to timeout. Your process was taking too long to complete, hence it was cancelled." )
               	
    except Exception as error:
        LOGGER(__name__).error(error)
        return await reply_msg.edit(
            "Something went wrong while generating Mediainfo from the given url.")


async def telegram_mediainfo(client, message, isRaw):
    """
    Generates Mediainfo from a Telegram File.
    """

    reply_msg = await message.reply_text(
        "Generating Mediainfo, Please wait...", quote=True)
    try:
        message = message.reply_to_message
        if message.text:
            return await message.reply_text(
                "Reply to a proper media file for generating Mediainfo.**", quote=True)

        if message.media.value == "video":
            media = message.video

        elif message.media.value == "audio":
            media = message.audio

        elif message.media.value == "document":
            media = message.document

        elif message.media.value == "voice":
            media = message.voice

        else:
            return await message.reply_text(
                "This type of media is not supported for generating Mediainfo.**",
                quote=True)

        filename = str(media.file_name)
        size = media.file_size
        
        rand_str = randstr()
        download_path = f"download/{rand_str}_{filename}"

        if int(size) <= 50000000:
            await message.download(os.path.join(os.getcwd(), download_path))

        else:
            async for chunk in client.stream_media(message, limit=5):
                with open(download_path, "ab") as f:
                    f.write(chunk)

        mediainfo = await async_subprocess(f"mediainfo '{download_path}'")
        mediainfo_json = await async_subprocess(
            f"mediainfo '{download_path}' --Output=JSON")
        mediainfo_json = json.loads(mediainfo_json)

        readable_size = get_readable_bytes(size)
        
        lines = mediainfo.splitlines()
        for i in range(len(lines)):
            if "Complete name" in lines[i]:
                lines[i] = re.sub(r": .+", ": " + unquote(filename), lines[i])

            if "File size" in lines[i]:
                lines[i] = re.sub(r": .+", ": " + readable_size, lines[i])

            elif (
                "Overall bit rate" in lines[i]
                and "Overall bit rate mode" not in lines[i]
            ):
                duration = float(mediainfo_json["media"]["track"][0]["Duration"])
                bitrate_kbps = (size * 8) / (duration * 1000)
                bitrate = get_readable_bitrate(bitrate_kbps)
                lines[i] = re.sub(r": .+", ": " + bitrate, lines[i])

            elif "IsTruncated" in lines[i] or "FileExtension_Invalid" in lines[i]:
                lines[i] = ""

        remove_N(lines)
        with open(f"{download_path}.txt", "w") as f:
            f.write("\n".join(lines))

        if isRaw:
            await message.reply_document(
                f"{download_path}.txt", caption=f"**File Name :** `{filename}`")
            os.remove(f"{download_path}.txt")
            os.remove(f"{download_path}")
            return await reply_msg.delete()

        with open(f"{download_path}.txt", "r+") as file:
            content = file.read()

        output = mediainfo_paste(text=content, title=filename)
        button = InlineKeyboardMarkup([
        [InlineKeyboardButton("View Mediainfo", url=output)]
    ])
        
        msg = f"<blockquote><code>{filename}</code></blockquote> \n**Size :** <code>{readable_size}</code>"
        
        await reply_msg.edit(
            text=msg,
            reply_markup=button,
            disable_web_page_preview=False
        )
        os.remove(f"{download_path}.txt")
        os.remove(download_path)

    except Exception as error:
        LOGGER(__name__).error(error)
        return await reply_msg.edit(
            "Something went wrong while generating Mediainfo from replied Telegram file.")


@Client.on_message(filters.command(["mediainfo", "m"]) & check_auth)
async def mediainfo(client, message: Message):
    mediainfo_usage = f"**Generates mediainfo from Google Drive Links, Telegram files or direct download links. \n\nReply to any telegram file or just pass the link after the command.\n\nUse `--r` flag for raw Mediainfo in document format."

    if message.reply_to_message:
        isRaw = False
        if len(message.command) > 1:
            user_input = message.text.split(None, 1)[1]
            isRaw = bool(re.search(r"(-|--)r", user_input))
        return await telegram_mediainfo(client, message, isRaw)

    if len(message.command) < 2:
        return await message.reply_text(mediainfo_usage, quote=True)

    user_input = message.text.split(None, 1)[1]
    isRaw = bool(re.search(r"(-|--)r", user_input))

    if url_match := re.search(r"https://drive\.google\.com/\S+", user_input):
        url = url_match.group(0)
        return await gdrive_mediainfo(message, url, isRaw)

    if url_match := re.search(
        r"https?://([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])",
        user_input,
    ):
        url = url_match.group(0)
        return await ddl_mediainfo(message, url, isRaw)
    return await message.reply_text(
        "This type of link is not supported.", quote=True)
