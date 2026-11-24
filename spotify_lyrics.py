"""
Spotify 桌面歌词浮窗（Windows / macOS）

- 拖动：移动位置
- 右键：隐藏 / 退出
- Windows 托盘图标：显示/隐藏、退出（左键双击托盘图标也可切换显示）

歌词来源: LRCLIB (lrclib.net)，免费、无需 API key。
"""
import os
import re
import sys
import time
import bisect
import asyncio
import threading
import subprocess
import tkinter as tk
from datetime import datetime, timezone

import requests

APP_NAME = "Spotify Lyrics"
POLL_INTERVAL = 0.5   # 多久读取一次播放状态（秒）
OFFSET = 0.3          # 歌词提前量（秒），觉得慢/快就调这个
UA = {"User-Agent": "spotify-desktop-lyrics/1.0"}
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"


def resource(name):
    """兼容 PyInstaller 打包后的资源路径"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def ensure_single_instance():
    """Windows 上防止重复打开多个窗口"""
    if not IS_WIN:
        return
    import ctypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    global _mutex
    _mutex = k32.CreateMutexW(None, False, "SpotifyDesktopLyricsMutex")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)


def enable_dpi_awareness():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


# ---------------- 读取 Spotify 当前播放 ----------------
def now_playing_mac():
    script = '''
    if application "Spotify" is running then
      tell application "Spotify"
        if player state is playing then
          return (name of current track) & "||" & (artist of current track) & "||" & ¬
                 (album of current track) & "||" & (duration of current track) & "||" & (player position)
        end if
      end tell
    end if
    return ""
    '''
    out = subprocess.run(["osascript", "-e", script],
                         capture_output=True, text=True).stdout.strip()
    if not out:
        return None
    title, artist, album, dur_ms, pos = out.split("||")
    return dict(title=title, artist=artist, album=album,
                duration=float(dur_ms.replace(",", ".")) / 1000,
                position=float(pos.replace(",", ".")))


async def _now_playing_win():
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as Manager)
    mgr = await Manager.request_async()
    for s in mgr.get_sessions():
        if "spotify" not in s.source_app_user_model_id.lower():
            continue
        if int(s.get_playback_info().playback_status) != 4:  # 4 = Playing
            return None
        props = await s.try_get_media_properties_async()
        tl = s.get_timeline_properties()
        pos = tl.position.total_seconds()
        try:  # Windows 的进度只在事件时更新，用 last_updated_time 补偿
            pos += (datetime.now(timezone.utc) - tl.last_updated_time).total_seconds()
        except Exception:
            pass
        return dict(title=props.title, artist=props.artist, album=props.album_title,
                    duration=tl.end_time.total_seconds(), position=pos)
    return None


def now_playing():
    try:
        if IS_MAC:
            return now_playing_mac()
        if IS_WIN:
            return asyncio.run(_now_playing_win())
    except Exception as e:
        print("读取播放状态失败:", e)
    return None


# ---------------- 获取并解析歌词 ----------------
def parse_lrc(text):
    lines = []
    for raw in text.splitlines():
        stamps = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", raw)
        content = re.sub(r"\[[^\]]*\]", "", raw).strip()
        for m, s in stamps:
            lines.append((int(m) * 60 + float(s), content))
    return sorted(lines)


def fetch_lyrics(t):
    try:
        r = requests.get("https://lrclib.net/api/get", headers=UA, timeout=8, params=dict(
            track_name=t["title"], artist_name=t["artist"],
            album_name=t["album"], duration=round(t["duration"])))
        data = r.json() if r.ok else None
        if not data or not data.get("syncedLyrics"):
            r = requests.get("https://lrclib.net/api/search", headers=UA, timeout=8,
                             params=dict(track_name=t["title"], artist_name=t["artist"]))
            data = next((x for x in r.json() if x.get("syncedLyrics")), None) if r.ok else None
        if data and data.get("syncedLyrics"):
            return parse_lrc(data["syncedLyrics"])
    except (requests.RequestException, ValueError) as e:
        print("获取歌词失败:", e)
    return []


# ---------------- 浮窗 ----------------
class App:
    def __init__(self):
        self.root = r = tk.Tk()
        r.title(APP_NAME)
        r.overrideredirect(True)          # 无边框
        r.attributes("-topmost", True)    # 置顶
        r.attributes("-alpha", 0.85)      # 半透明
        r.configure(bg="black")
        w, h = 900, 90
        r.geometry(f"{w}x{h}+{(r.winfo_screenwidth() - w) // 2}+{r.winfo_screenheight() - 200}")

        font = "Microsoft YaHei" if IS_WIN else "Helvetica"
        self.cur = tk.Label(r, fg="white", bg="black", font=(font, 24, "bold"))
        self.nxt = tk.Label(r, fg="#888888", bg="black", font=(font, 15))
        self.cur.pack(expand=True)
        self.nxt.pack(pady=(0, 8))

        # 右键菜单
        self.menu = tk.Menu(r, tearoff=0)
        if IS_WIN:
            self.menu.add_command(label="隐藏（托盘图标可恢复）", command=self._toggle)
        self.menu.add_command(label="退出", command=self._request_quit)

        for widget in (r, self.cur, self.nxt):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<Button-3>", self._popup)
            if IS_MAC:
                widget.bind("<Button-2>", self._popup)

        self.key = None
        self.lyrics, self.times = [], []
        self.pos, self.stamp, self.playing = 0.0, time.time(), False
        self.visible, self.want_visible, self.quitting = True, True, False
        self.tray = None

        self._start_tray()
        threading.Thread(target=self._worker, daemon=True).start()
        self._render()

    # ----- 交互 -----
    def _start_drag(self, e):
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _popup(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def _toggle(self):
        self.want_visible = not self.want_visible

    def _request_quit(self):
        self.quitting = True

    def _start_tray(self):
        if not IS_WIN:
            return
        try:
            import pystray
            from PIL import Image
            menu = pystray.Menu(
                pystray.MenuItem("显示/隐藏", lambda icon, item: self._toggle(), default=True),
                pystray.MenuItem("退出", lambda icon, item: self._request_quit()))
            self.tray = pystray.Icon("SpotifyLyrics", Image.open(resource("icon.ico")),
                                     "Spotify 桌面歌词", menu)
            self.tray.run_detached()
        except Exception as e:
            print("托盘图标启动失败:", e)

    # ----- 后台：读状态、拉歌词 -----
    def _worker(self):
        while not self.quitting:
            np = now_playing()
            if np:
                key = (np["title"], np["artist"])
                if key != self.key:
                    self.key, self.lyrics, self.times = key, [], []
                    lyrics = fetch_lyrics(np)
                    if self.key == key:
                        self.lyrics = lyrics or [(0, f"{np['title']} — {np['artist']}（没找到同步歌词）")]
                        self.times = [t for t, _ in self.lyrics]
                self.pos, self.stamp, self.playing = np["position"], time.time(), True
            else:
                self.playing = False
            time.sleep(POLL_INTERVAL)

    # ----- 主线程：刷新界面 -----
    def _render(self):
        if self.quitting:
            if self.tray:
                self.tray.stop()
            self.root.destroy()
            return

        if self.want_visible != self.visible:
            self.visible = self.want_visible
            if self.visible:
                self.root.deiconify()
                self.root.attributes("-topmost", True)
            else:
                self.root.withdraw()

        if self.lyrics:
            pos = self.pos + (time.time() - self.stamp if self.playing else 0) + OFFSET
            i = bisect.bisect_right(self.times, pos) - 1
            cur = self.lyrics[i][1] if i >= 0 else "♪"
            nxt = self.lyrics[i + 1][1] if i + 1 < len(self.lyrics) else ""
            self.cur.config(text=cur or "♪")
            self.nxt.config(text=nxt)
        else:
            self.cur.config(text="等待 Spotify 播放…" if not self.key else "加载歌词中…")
            self.nxt.config(text="")
        self.root.after(100, self._render)


if __name__ == "__main__":
    ensure_single_instance()
    enable_dpi_awareness()
    App().root.mainloop()
