import flet as ft
import threading
import requests
import time

class MinimalDiscordBot:
    def __init__(self, token, channel_id, base_bet, cooldown, max_bet, log_cb, stat_cb, dm_cb):
        self.token = token
        self.channel_id = str(channel_id)
        self.base_bet = int(base_bet)
        self.current_bet = self.base_bet
        self.cooldown = int(cooldown)
        self.max_bet = int(max_bet)
        
        self.log = log_cb
        self.update_stats = stat_cb
        self.show_notification = dm_cb
        
        self.running = False
        self.total_wins = 0
        self.total_losses = 0
        self.profit = 0
        
        self.owo_id = "408785106942164992"

    def send_message(self, content):
        url = f"https://discord.com/api/v9/channels/{self.channel_id}/messages"
        headers = {"Authorization": self.token, "Content-Type": "application/json"}
        payload = {"content": content}
        try:
            r = requests.post(url, headers=headers, json=payload)
            return r.status_code == 200
        except Exception as e:
            return False

    def fetch_messages(self):
        url = f"https://discord.com/api/v9/channels/{self.channel_id}/messages?limit=5"
        headers = {"Authorization": self.token}
        try:
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return []

    def check_message_content(self, msg_data):
        if str(msg_data.get("author", {}).get("id")) != self.owo_id:
            return None
            
        content = (msg_data.get("content") or "").lower()
        embeds = msg_data.get("embeds", [])
        for emb in embeds:
            content += " " + (emb.get("description") or "").lower()
            content += " " + (emb.get("title") or "").lower()
            
        if "captcha" in content or "verify" in content or "human" in content or "type the code" in content:
            return "captcha"
        if "and you won" in content:
            return "win"
        if "and you lost" in content:
            return "loss"
        return None

    def bot_loop(self):
        self.log("✅ Bot running via HTTP Polling!", "green")
        while self.running:
            if self.current_bet > self.max_bet:
                self.log(f"⚠️ Max bet hit ({self.current_bet}). Resetting.", "orange")
                self.current_bet = self.base_bet
                
            cmd = f"owo cf {self.current_bet}"
            self.log(f"🎲 Sending: {cmd}", "blue")
            
            success = self.send_message(cmd)
            if not success:
                self.log("❌ Failed to send message.", "red")
                time.sleep(self.cooldown)
                continue
            
            # Poll for 15 seconds to wait for result
            result_found = False
            start_wait = time.time()
            
            while time.time() - start_wait < 15.0 and self.running:
                time.sleep(2) # check every 2 seconds
                msgs = self.fetch_messages()
                
                for m in msgs:
                    # check if message is newer than our send time
                    res = self.check_message_content(m)
                    
                    if res == "captcha":
                        self.log("🚨 CAPTCHA DETECTED! Pausing.", "red")
                        self.show_notification("CAPTCHA DETECTED", "Open Discord to solve it!")
                        self.running = False
                        return
                    elif res == "win":
                        self.total_wins += 1
                        self.profit += self.current_bet
                        self.log(f"🏆 Won {self.current_bet}! Reset to {self.base_bet}.", "green")
                        self.current_bet = self.base_bet
                        result_found = True
                        break
                    elif res == "loss":
                        self.total_losses += 1
                        self.profit -= self.current_bet
                        new_bet = self.current_bet * 2
                        self.log(f"💀 Lost {self.current_bet}. Doubling to {new_bet}.", "red")
                        self.current_bet = new_bet
                        result_found = True
                        break
                        
                if result_found:
                    break
                    
            if not result_found and self.running:
                self.log("⚠️ No response from OWO. Retrying.", "orange")
            elif result_found:
                self.update_stats(self.total_wins, self.total_losses, self.profit)
            
            if self.running:
                time.sleep(self.cooldown)

    def start(self):
        self.running = True
        threading.Thread(target=self.bot_loop, daemon=True).start()

    def stop(self):
        self.running = False


def main(page: ft.Page):
    page.title = "SPR OWO AUTO BOT"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.ADAPTIVE

    bot_instance = None
    
    try:
        from flet_permission_handler import PermissionHandler, PermissionType
        import flet_android_notifications as fan
        
        ph = PermissionHandler()
        page.overlay.append(ph)
        
        notifications = fan.FletAndroidNotifications()
        page.overlay.append(notifications)
        
        def on_page_load(e):
            ph.request_permissions([PermissionType.NOTIFICATION])
            notifications.init()
            notifications.create_notification_channel("owo_alerts", "OWO Alerts", "Alerts for Captcha")
            
        page.on_connect = on_page_load
    except ImportError:
        notifications = None
        ph = None

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

    def show_notification(title, text):
        if notifications:
            try:
                notifications.show_notification(
                    id=1,
                    title=title,
                    body=text,
                    channel_id="owo_alerts"
                )
            except:
                pass
                
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"{title}: {text}", color="white", weight="bold"),
            bgcolor="red"
        )
        page.snack_bar.open = True
        page.update()

    def start_bot(e):
        nonlocal bot_instance
        if not token_input.value or not channel_input.value:
            log("❌ Token and Channel ID are required!", "red")
            return
        
        if btn_start.text == "Start Bot":
            btn_start.text = "Stop Bot"
            btn_start.bgcolor = ft.colors.RED_700
            page.update()
            
            bot_instance = MinimalDiscordBot(
                token_input.value,
                channel_input.value,
                base_input.value,
                cd_input.value,
                max_input.value,
                log,
                update_stats,
                show_notification
            )
            log("🔄 Connecting to Discord...", "yellow")
            bot_instance.start()
        else:
            if bot_instance:
                bot_instance.stop()
            
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
            ft.Row([base_input, max_input, cd_input], alignment=ft.MainAxisAlignment.CENTER),
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
