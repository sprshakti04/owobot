import flet as ft
import asyncio
import discord
from discord.ext import tasks
import sys

class OWOBot(discord.Client):
    def __init__(self, token, channel_id, base_bet, cooldown, max_bet, log_callback, stat_callback):
        super().__init__()
        self.token_str = token
        self.channel_id = int(channel_id)
        self.base_bet = int(base_bet)
        self.current_bet = self.base_bet
        self.cooldown = int(cooldown)
        self.max_bet = int(max_bet)
        
        self.log = log_callback
        self.update_stats = stat_callback
        
        self.running_loop = False
        self.total_wins = 0
        self.total_losses = 0
        self.profit = 0
        
        self.owo_id = 408785106942164992
        self._waiting_result = False
        self._result_event = asyncio.Event()
        self._last_result = None
        self.channel = None

    async def on_ready(self):
        self.log(f"✅ Logged in as {self.user}", "green")
        try:
            self.channel = await self.fetch_channel(self.channel_id)
            self.log(f"✅ Channel Found: #{self.channel.name}", "green")
            self.running_loop = True
            self.bot_loop.start()
        except Exception as e:
            self.log(f"❌ Could not find channel: {e}", "red")

    async def on_message(self, message):
        await self._check_captcha(message)
        await self._check_result(message)

    async def on_message_edit(self, before, after):
        await self._check_captcha(after)
        await self._check_result(after)

    async def _check_captcha(self, message):
        if message.channel.id != self.channel_id or message.author.id != self.owo_id:
            return
        
        text = message.content.lower()
        if message.embeds:
            for emb in message.embeds:
                if emb.description: text += emb.description.lower()
                if emb.title: text += emb.title.lower()

        captcha_kws = ["captcha", "verify", "human verification", "type the code"]
        if any(kw in text for kw in captcha_kws):
            self.log("🚨 CAPTCHA DETECTED! Bot paused.", "red")
            self.running_loop = False
            if self.bot_loop.is_running():
                self.bot_loop.cancel()

    async def _check_result(self, message):
        if not self._waiting_result or message.channel.id != self.channel_id or message.author.id != self.owo_id:
            return

        text = message.content.lower()
        if message.embeds:
            for emb in message.embeds:
                if emb.description: text += emb.description.lower()
                if emb.title: text += emb.title.lower()

        if "and you won" in text:
            self._last_result = "win"
            self._result_event.set()
        elif "and you lost" in text:
            self._last_result = "loss"
            self._result_event.set()

    @tasks.loop(seconds=1)
    async def bot_loop(self):
        if not self.running_loop:
            return

        # Cap check
        if self.current_bet > self.max_bet:
            self.log(f"⚠️ Max bet hit ({self.current_bet}). Resetting.", "orange")
            self.current_bet = self.base_bet

        cmd = f"owo cf {self.current_bet}"
        self.log(f"🎲 Sending: {cmd}", "blue")
        
        self._last_result = None
        self._result_event.clear()
        self._waiting_result = True

        try:
            await self.channel.send(cmd)
        except Exception as e:
            self.log(f"❌ Failed to send: {e}", "red")
            self.bot_loop.change_interval(seconds=self.cooldown)
            return

        try:
            await asyncio.wait_for(self._result_event.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            self.log("⚠️ No response from OWO. Retrying next round.", "orange")
            self._waiting_result = False
            self.bot_loop.change_interval(seconds=self.cooldown)
            return

        self._waiting_result = False

        if self._last_result == "win":
            self.total_wins += 1
            self.profit += self.current_bet
            self.log(f"🏆 Won {self.current_bet}! Resetting to {self.base_bet}.", "green")
            self.current_bet = self.base_bet
        elif self._last_result == "loss":
            self.total_losses += 1
            self.profit -= self.current_bet
            new_bet = self.current_bet * 2
            self.log(f"💀 Lost {self.current_bet}. Doubling to {new_bet}.", "red")
            self.current_bet = new_bet
        
        self.update_stats(self.total_wins, self.total_losses, self.profit)
        self.bot_loop.change_interval(seconds=self.cooldown)


def main(page: ft.Page):
    page.title = "SPR OWO AUTO BOT"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.ADAPTIVE

    bot_instance = None
    bot_task = None

    def log(msg, color="white"):
        logs_view.controls.append(ft.Text(msg, color=color))
        if len(logs_view.controls) > 50:
            logs_view.controls.pop(0)
        page.update()

    def update_stats(wins, losses, profit):
        win_txt.value = str(wins)
        loss_txt.value = str(losses)
        prof_txt.value = f"{profit} cw"
        prof_txt.color = "green" if profit >= 0 else "red"
        page.update()

    async def start_bot(e):
        nonlocal bot_instance, bot_task
        if not token_input.value or not channel_input.value:
            log("❌ Token and Channel ID are required!", "red")
            return
        
        if btn_start.text == "Start Bot":
            btn_start.text = "Stop Bot"
            btn_start.bgcolor = ft.colors.RED_700
            page.update()
            
            bot_instance = OWOBot(
                token_input.value,
                channel_input.value,
                base_input.value,
                cd_input.value,
                max_input.value,
                log,
                update_stats
            )
            log("🔄 Connecting to Discord...", "yellow")
            bot_task = asyncio.create_task(bot_instance.start(token_input.value))
        else:
            if bot_instance:
                bot_instance.running_loop = False
                await bot_instance.close()
            if bot_task:
                bot_task.cancel()
            
            btn_start.text = "Start Bot"
            btn_start.bgcolor = ft.colors.BLUE_700
            log("🛑 Bot stopped.", "red")
            page.update()

    # --- UI Elements ---
    title = ft.Text("SPR OWO AUTO BOT", size=30, weight="bold", color=ft.colors.BLUE_400)
    
    token_input = ft.TextField(label="Auth Token", password=True, can_reveal_password=True, width=400)
    channel_input = ft.TextField(label="Channel ID", width=400)
    
    base_input = ft.TextField(label="Base Bet", value="100", width=120)
    max_input = ft.TextField(label="Max Bet", value="100000", width=120)
    cd_input = ft.TextField(label="Cooldown (s)", value="15", width=120)

    btn_start = ft.ElevatedButton("Start Bot", on_click=start_bot, bgcolor=ft.colors.BLUE_700, color=ft.colors.WHITE, width=200, height=50)

    win_txt = ft.Text("0", size=24, weight="bold", color="green")
    loss_txt = ft.Text("0", size=24, weight="bold", color="red")
    prof_txt = ft.Text("0 cw", size=24, weight="bold", color="white")

    stats_row = ft.Row([
        ft.Column([ft.Text("WINS"), win_txt], horizontal_alignment="center"),
        ft.Container(width=30),
        ft.Column([ft.Text("LOSSES"), loss_txt], horizontal_alignment="center"),
        ft.Container(width=30),
        ft.Column([ft.Text("PROFIT"), prof_txt], horizontal_alignment="center"),
    ], alignment=ft.MainAxisAlignment.CENTER)

    logs_view = ft.ListView(expand=True, spacing=5, auto_scroll=True, height=300)
    log_container = ft.Container(
        content=logs_view,
        border=ft.border.all(1, ft.colors.OUTLINE),
        border_radius=10,
        padding=10,
        bgcolor=ft.colors.SURFACE_VARIANT
    )

    page.add(
        ft.Column([
            title,
            ft.Text("Login Settings", weight="bold"),
            token_input,
            channel_input,
            ft.Divider(),
            ft.Text("Bet Settings", weight="bold"),
            ft.Row([base_input, max_input, cd_input]),
            ft.Container(height=10),
            ft.Row([btn_start], alignment=ft.MainAxisAlignment.CENTER),
            ft.Divider(),
            stats_row,
            ft.Container(height=10),
            ft.Text("Live Logs", weight="bold"),
            log_container
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )

if __name__ == "__main__":
    ft.app(target=main)
