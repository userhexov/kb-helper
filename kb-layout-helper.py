#!/usr/bin/env python3
"""
kb-layout-helper – управление раскладкой клавиатуры для Hyprland
Функции:
- переключение раскладки по активному окну (window_rules)
- авто-детект транслитерации (например, "ghbdtn" -> "привет") с уведомлением через swaync
Конфигурация: ~/.config/kb-layout-helper/config.conf
"""

import configparser
import json
import os
import socket
import subprocess
import sys
import threading
import time
import re
from datetime import datetime

# Попытка импорта evdev (для авто-детекта)
try:
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

# ------------------ Логирование ------------------
LOG_FILE = os.path.expanduser("~/.config/kb-layout-helper/helper.log")
def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {msg}\n")
    except:
        pass

# ------------------ Чтение конфига ------------------
def load_config():
    config = configparser.ConfigParser()
    config.optionxform = str  # сохраняем регистр ключей
    config.read(os.path.expanduser("~/.config/kb-layout-helper/config.conf"))
    return config

# ------------------ Работа с Hyprland ------------------
def get_keyboard_device(config):
    dev_name = config.get("DEFAULT", "main_device", fallback="auto")
    if dev_name != "auto":
        return dev_name
    try:
        result = subprocess.run(["hyprctl", "devices", "-j"], capture_output=True, text=True, check=True)
        devices = json.loads(result.stdout)
        # ищем клавиатуру с main = true
        for dev in devices.get("keyboards", []):
            if dev.get("main", False):
                return dev["name"]
        # иначе первую не power-button
        for dev in devices.get("keyboards", []):
            if "power-button" not in dev["name"].lower():
                return dev["name"]
    except Exception as e:
        log(f"Ошибка определения клавиатуры: {e}")
    return None

def get_current_layout_index(device):
    try:
        result = subprocess.run(["hyprctl", "devices", "-j"], capture_output=True, text=True, check=True)
        devices = json.loads(result.stdout)
        for dev in devices.get("keyboards", []):
            if dev["name"] == device:
                keymap = dev.get("active_keymap", "")
                if "US" in keymap or "English" in keymap:
                    return 0
                elif "Russian" in keymap or "RU" in keymap:
                    return 1
    except Exception as e:
        log(f"Ошибка получения раскладки: {e}")
    return -1

def switch_layout(device, index):
    subprocess.run(["hyprctl", "switchxkblayout", device, str(index)], check=False)

# ------------------ Модуль переключения по окнам ------------------
class WindowWatcher:
    def __init__(self, config, device):
        self.device = device
        self.rules = {}
        self.saved = {}
        self.last_addr = None
        if config.has_section("window_rules"):
            for key, val in config.items("window_rules"):
                if val.lower() == "us":
                    self.rules[key] = 0
                elif val.lower() == "ru":
                    self.rules[key] = 1
        log(f"WindowWatcher: правила {self.rules}")

    def active_info(self):
        try:
            out = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, check=True)
            data = json.loads(out.stdout)
            return data.get("address"), data.get("class")
        except:
            return None, None

    def handle(self):
        addr, cls = self.active_info()
        if not addr or not cls:
            return
        if addr == self.last_addr:
            return

        # сохранить раскладку для старого окна
        if self.last_addr is not None:
            cur = get_current_layout_index(self.device)
            if cur != -1:
                self.saved[self.last_addr] = cur

        # применить для нового
        if addr in self.saved:
            target = self.saved[addr]
            cur = get_current_layout_index(self.device)
            if cur != target:
                switch_layout(self.device, target)
                log(f"Восстановлена раскладка {target} для {cls}")
        elif cls in self.rules:
            target = self.rules[cls]
            cur = get_current_layout_index(self.device)
            if cur != target:
                if cur != -1:
                    self.saved[addr] = cur
                switch_layout(self.device, target)
                log(f"Применена раскладка {target} для {cls}")

        self.last_addr = addr

    def run(self):
        instance = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        if not instance:
            log("WindowWatcher: HYPRLAND_INSTANCE_SIGNATURE отсутствует")
            return
        sock_path = f"{os.environ.get('XDG_RUNTIME_DIR', '/run/user/1000')}/hypr/{instance}/.socket2.sock"
        if not os.path.exists(sock_path):
            log(f"WindowWatcher: сокет не найден {sock_path}")
            return

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(sock_path)
            with sock.makefile('r') as f:
                while True:
                    line = f.readline()
                    if not line:
                        continue
                    if line.startswith("activewindow>>") or line.startswith("activewindowv2>>"):
                        self.handle()
                    time.sleep(0.05)  # небольшая пауза

# ------------------ Модуль авто-детекта транслитерации ------------------
# Таблица перевода латиницы в русские буквы (английская раскладка -> русская)
TRANS_TABLE = {
    'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з',
    '[': 'х', ']': 'ъ', 'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л',
    'l': 'д', ';': 'ж', "'": 'э', 'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь',
    ',': 'б', '.': 'ю', '/': '.'
}

class AutoDetect:
    def __init__(self, config):
        self.enabled = config.getboolean("auto_detect", "enabled", fallback=False)
        self.threshold = config.getint("auto_detect", "threshold", fallback=4)
        self.notify = config.getboolean("auto_detect", "notify", fallback=True)
        self.auto_switch = config.getboolean("auto_detect", "auto_switch", fallback=False)
        dev_path = config.get("auto_detect", "keyboard_device", fallback="auto")
        if dev_path == "auto":
            # попробуем найти устройство автоматически через evdev
            self.device_path = self._find_keyboard_device()
        else:
            self.device_path = dev_path
        self.buffer = ""
        self.last_time = time.time()
        self.last_notify = 0
        self.notify_cooldown = 10  # секунд

    def _find_keyboard_device(self):
        """Пытается найти устройство клавиатуры через evdev (простая эвристика)"""
        if not EVDEV_AVAILABLE:
            return None
        try:
            from evdev import list_devices, InputDevice
            for path in list_devices('/dev/input/'):
                dev = InputDevice(path)
                if 'keyboard' in dev.name.lower() or 'kbd' in dev.name.lower():
                    if 'power' not in dev.name.lower() and 'mouse' not in dev.name.lower():
                        return path
            # если не нашли, вернём None
        except:
            pass
        return None

    def is_translit_candidate(self, word):
        """Проверяет, похоже ли слово на русское, набранное в английской раскладке."""
        if len(word) < self.threshold:
            return False
        # Если в слове есть русские буквы, это не транслит
        if re.search(r'[а-яё]', word.lower()):
            return False
        # Транслитерируем
        rus_word = ''.join(TRANS_TABLE.get(ch, ch) for ch in word.lower())
        # Если после транслитерации появились русские буквы и есть хотя бы одна гласная
        if any(c in 'аеёиоуыэюя' for c in rus_word):
            return True
        return False

    def show_notification(self, word, rus_word):
        if not self.notify:
            return
        now = time.time()
        if now - self.last_notify < self.notify_cooldown:
            return
        self.last_notify = now
        subprocess.run([
            "notify-send",
            "-a", "kb-layout-helper",
            "-u", "normal",
            "-t", "5000",
            "Возможно, вы набираете русский текст",
            f"Слово '{word}' похоже на '{rus_word}'. Переключите раскладку на русскую."
        ], check=False)

    def run(self):
        if not self.enabled:
            log("AutoDetect: отключён")
            return
        if not EVDEV_AVAILABLE:
            log("AutoDetect: evdev не установлен, модуль не работает")
            return
        if not self.device_path:
            log("AutoDetect: не удалось определить устройство клавиатуры")
            return

        try:
            dev = InputDevice(self.device_path)
        except Exception as e:
            log(f"AutoDetect: не удалось открыть {self.device_path}: {e}")
            return

        # Маппинг scancode -> символ (только для букв a-z)
        code_map = {
            16: 'q', 17: 'w', 18: 'e', 19: 'r', 20: 't', 21: 'y', 22: 'u', 23: 'i', 24: 'o', 25: 'p',
            30: 'a', 31: 's', 32: 'd', 33: 'f', 34: 'g', 35: 'h', 36: 'j', 37: 'k', 38: 'l',
            44: 'z', 45: 'x', 46: 'c', 47: 'v', 48: 'b', 49: 'n', 50: 'm',
        }
        log(f"AutoDetect: слушаю {self.device_path}")

        for event in dev.read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:  # нажатие
                code = event.code
                if code in code_map:
                    self.buffer += code_map[code]
                elif code == 57:      # пробел
                    if self.buffer:
                        if self.is_translit_candidate(self.buffer):
                            rus = ''.join(TRANS_TABLE.get(ch, ch) for ch in self.buffer.lower())
                            log(f"Обнаружен транслит: '{self.buffer}' -> '{rus}'")
                            self.show_notification(self.buffer, rus)
                            if self.auto_switch:
                                device = get_keyboard_device(load_config())
                                if device:
                                    cur = get_current_layout_index(device)
                                    if cur != 1:
                                        switch_layout(device, 1)
                                        log("AutoDetect: автоматически переключил на русскую")
                        self.buffer = ""
                elif code == 28:      # enter
                    if self.buffer:
                        if self.is_translit_candidate(self.buffer):
                            rus = ''.join(TRANS_TABLE.get(ch, ch) for ch in self.buffer.lower())
                            log(f"Обнаружен транслит: '{self.buffer}' -> '{rus}'")
                            self.show_notification(self.buffer, rus)
                            if self.auto_switch:
                                device = get_keyboard_device(load_config())
                                if device:
                                    cur = get_current_layout_index(device)
                                    if cur != 1:
                                        switch_layout(device, 1)
                                        log("AutoDetect: автоматически переключил на русскую")
                        self.buffer = ""
                elif code == 14:      # backspace
                    self.buffer = self.buffer[:-1]
                # сброс по таймауту
                if time.time() - self.last_time > 2:
                    self.buffer = ""
                self.last_time = time.time()

# ------------------ Запуск ------------------
def main():
    config = load_config()
    device = get_keyboard_device(config)
    if not device:
        log("Не удалось определить клавиатуру, выходим")
        sys.exit(1)

    # Запускаем модуль переключения по окнам (если есть правила)
    if config.has_section("window_rules") and config.items("window_rules"):
        watcher = WindowWatcher(config, device)
        threading.Thread(target=watcher.run, daemon=True).start()
    else:
        log("Нет правил для окон, WindowWatcher не запущен")

    # Запускаем авто-детект (если включён)
    if config.getboolean("auto_detect", "enabled", fallback=False):
        detector = AutoDetect(config)
        threading.Thread(target=detector.run, daemon=True).start()
    else:
        log("AutoDetect отключён")

    # Держим главный поток живым
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Завершение работы")

if __name__ == "__main__":
    main()
