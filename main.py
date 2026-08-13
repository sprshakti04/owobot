import flet as ft
import websocket
import json
import threading
import requests
import time

class MinimalDiscordBot:
    def __init__(self, token, channel_id, base_bet, cooldown, max_bet, log_cb, stat_cb):
        self.token = token
        self.channel_id = str(channel_id)
        self.base_bet = int(base_bet)
        self.current_bet = self.base_bet
        self.cooldown = int(cooldown)
        self.max_bet = int(max_bet)
        
        self.log = log_cb
        self.update_stats = stat_cb
        
        self.running = False
        self.total_wins = 0
        self.total_losses = 0
        self.profit = 0
        
        self.ws = None
        self.owo_id = "408785106942164992"
        self._waiting_result = False
        self._result_event = threading.Event()
        self._last_result = None

    def send_message(self, content):
        url = f"https://discord.com/api/v9/channels/{self.channel_id}/messages"
        headers = {"Authorization": self.token, "Content-Type": "application/json"}
        payload = {"content": content}
        try:
            r = requests.post(url, headers=headers, json=payload)
            return r.status_code == 200
        except Exception as e:
            return False

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            op = data.get("op")
            t = data.get("t")
            d = data.get("d")
            
            if op == 10: # Hello
                heartbeat_interval = d["heartbeat_interval"] / 1000
                threading.Thread(target=self.heartbeat, args=(heartbeat_interval,), daemon=True).start()
                
                payload = {
                    "op": 2,
                    "d": {
                        "token": self.token,
                        "capabilities": 16381,
                        "properties": {
                            "os": "Windows",
                            "browser": "Chrome",
                            "device": "",
                        }
                    }
                }
                ws.send(json.dumps(payload))
                
            elif t in ["MESSAGE_CREATE", "MESSAGE_UPDATE"] and d:
                if str(d.get("channel_id")) == self.channel_id and str(d.get("author", {}).get("id")) == self.owo_id:
                    content = (d.get("content") or "").lower()
                    embeds = d.get("embeds", [])
                    for emb in embeds:
                        content += " " + (emb.get("description") or "").lower()
                        content += " " + (emb.get("title") or "").lower()
                    
                    if "captcha" in content or "verify" in content or "human" in content or "type the code" in content:
                        self.log("🚨 CAPTCHA DETECTED! Pausing.", "red")
                        self.running = False
                        return
                    
                    if self._waiting_result:
                        if "and you won" in content:
                            self._last_result = "win"
                            self._result_event.set()
                        elif "and you lost" in content:
                            self._last_result = "loss"
                            self._result_event.set()
        except Exception as e:
            pass

    def heartbeat(self, interval):
        while self.running and self.ws:
            time.sleep(interval)
            try:
                self.ws.send(json.dumps({"op": 1, "d": None}))
            except:
                break

    def bot_loop(self):
        # Small delay to let WS connect
        time.sleep(2)
        while self.running:
            if self.current_bet > self.max_bet:
                self.log(f"⚠️ Max bet hit ({self.current_bet}). Resetting.", "orange")
                self.current_bet = self.base_bet
                
            cmd = f"owo cf {self.current_bet}"
            self.log(f"🎲 Sending: {cmd}", "blue")
            
            self._last_result = None
            self._result_event.clear()
            self._waiting_result = True
            
            success = self.send_message(cmd)
            if not success:
                self.log("❌ Failed to send message.", "red")
            else:
                hit = self._result_event.wait(timeout=15.0)
                if not hit:
                    self.log("⚠️ No response from OWO. Retrying.", "orange")
                else:
                    if self._last_result == "win":
                        self.total_wins += 1
                        self.profit += self.current_bet
                        self.log(f"🏆 Won {self.current_bet}! Reset to {self.base_bet}.", "green")
                        self.current_bet = self.base_bet
                    elif self._last_result == "loss":
                        self.total_losses += 1
                        self.profit -= self.current_bet
                        new_bet = self.current_bet * 2
                        self.log(f"💀 Lost {self.current_bet}. Doubling to {new_bet}.", "red")
                        self.current_bet = new_bet
                        
                    self.update_stats(self.total_wins, self.total_losses, self.profit)
            
            if self.running:
                time.sleep(self.cooldown)

    def start(self):
        self.running = True
        self.ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json",
                                         on_message=self.on_message)
        
        threading.Thread(target=self.ws.run_forever, daemon=True).start()
        threading.Thread(target=self.bot_loop, daemon=True).start()
        self.log("✅ Bot connected and running!", "green")

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()


def main(page: ft.Page):
    page.title = "SPR OWO AUTO BOT"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.ADAPTIVE

    bot_instance = None

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
                update_stats
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
