from datetime import datetime
from discord import Embed
from discord.ext import tasks, commands
from file_read_backwards import FileReadBackwards
import glob
import re

import embed


class ChatHandler(commands.Cog):
    """Class which handles the chat log files"""

    def __init__(self, bot, logPath, serverMessages):
        self.bot = bot
        self.logPath = logPath
        self.serverMessages = serverMessages
        self.lastUpdateTimestamp = datetime.now()
        self.update.start()
        self.webhook = None

    def splitLine(self, line: str) -> tuple[datetime, str]:
        """Split a log line into a timestamp and the remaining message"""
        timestampStr, message = line.strip()[1:].split("]", 1)
        timestamp = datetime.strptime(timestampStr, "%d-%m-%y %H:%M:%S.%f")
        return timestamp, message

    @tasks.loop(seconds=2)
    async def update(self) -> None:
        """Update the handler

        This will check the latest log file and update our data based on any
        new entries
        """
        files = glob.glob(self.logPath + "/*chat.txt")
        if len(files) > 0:
            with FileReadBackwards(files[0], encoding="latin-1") as f:
                newTimestamp = self.lastUpdateTimestamp
                for line in f:
                    timestamp, message = self.splitLine(line)
                    if timestamp > newTimestamp:
                        newTimestamp = timestamp
                    if timestamp > self.lastUpdateTimestamp:
                        await self.handleLog(timestamp, message)
                    else:
                        break
                self.lastUpdateTimestamp = newTimestamp

    async def handleLog(self, timestamp: datetime, message: str) -> Embed | None:
        """Parse the given line from the logfile and mirror chat message in
        discord if necessary"""

        # # Ignore anything that's not "General" chat or a server announcement
        match = re.search(r"^(?:\[info\] Message ChatMessage\{chat=General, author=| Server alert message: )\'", message)
        if  match and self.bot.channel is not None:
            pattern = r"(?:] Message.*chat=General, author=\'|^ )(.*)(?:\', text=| alert message: )\'(.*)\'"
            match_data = re.search(pattern, message)

            isServer = match_data.group(1) == "Server"
            # Exit if it is a server announcement but server message handling setting is disabled
            # [07-11-25 21:59:34.725] Server alert message: 'dasdasd' sent..
            if isServer and not self.serverMessages:
                return

            if match and self.bot.channel is not None:
                # Use a webhook to make it look like we're the discord member
                # God bless stack overflow
                if self.bot.channel:
                    for webhook in await self.bot.channel.webhooks():
                        if webhook.user == self.bot.user:
                            self.webhook = webhook
                if self.webhook is None:
                    self.webhook = await self.bot.channel.create_webhook(name="zomboi")

                if isServer:
                    name = "PZ Discord integration"
                else:
                    name = match_data.group(1)
                avatar_url = None
                message = match_data.group(2)

                for member in self.bot.get_all_members():
                    if match_data.group(1) in member.display_name:
                        avatar_url = member.display_avatar
                if isServer:
                    await self.webhook.send(
                        # embed=embed.server_message(message),
                        message=message,
                        username="Server announcement",
                        avatar_url=avatar_url,
                        suppress_embeds=True,
                    )
                else:
                    await self.webhook.send(
                        embed=embed.chat_message(timestamp, message),
                        username=name,
                        avatar_url=avatar_url,
                        suppress_embeds=True,
                    )
