# kb-layout-helper

Утилита для управления раскладкой клавиатуры в окружении [Hyprland](https://hyprland.org/).

## Возможности

- **Переключение раскладки по активному окну** — запоминает раскладку для каждого окна и восстанавливает её при переключении. Поддерживаются правила для классов окон (например, терминал всегда US, а мессенджер — RU).
- **Авто-детект транслитерации** — анализирует вводимый текст и при обнаружении слова, похожего на русское, набранное в английской раскладке (например, `ghbdtn` → `привет`), показывает уведомление и опционально переключает раскладку на русскую.

## Установка

1. Клонируйте репозиторий (или скопируйте скрипт в удобное место):
  
   git clone https://github.com/yourusername/kb-layout-helper.git
   cd kb-layout-helper

    Установите зависимости:
    bash

    pip install evdev

    Если вы не планируете использовать авто-детект, evdev можно не ставить.

    Создайте конфигурационный файл (см. CONFIG.md):
    bash

    mkdir -p ~/.config/kb-layout-helper
    cp config.example.conf ~/.config/kb-layout-helper/config.conf
    # отредактируйте config.conf под свои нужды

    Сделайте скрипт исполняемым:
    bash

    chmod +x kb-layout-helper.py

Использование

Запустите скрипт:
bash

./kb-layout-helper.py

Для автоматического запуска при старте Hyprland добавьте в конфиг Hyprland (например, ~/.config/hypr/hyprland.conf):
ini

exec-once = /путь/к/kb-layout-helper.py

Скрипт работает в фоне, логи пишутся в ~/.config/kb-layout-helper/helper.log.
Требования

    Python 3.6+

    Hyprland (с поддержкой hyprctl и сокетов)

    evdev (опционально, для авто-детекта)

    notify-send (для уведомлений, обычно входит в libnotify)

Конфигурация

Подробное описание всех параметров конфигурации смотрите в CONFIG.md.
Лицензия

MIT
text


---

## CONFIG.md


# Конфигурация kb-layout-helper

Файл конфигурации: `~/.config/kb-layout-helper/config.conf`

Формат — стандартный INI (секции и ключи). Пример полного конфига:

[DEFAULT]
main_device = auto

[window_rules]
Alacritty = us
firefox = ru
org.wezfurlong.wezterm = us

[auto_detect]
enabled = true
threshold = 4
notify = true
auto_switch = false
keyboard_device = auto

Секция [DEFAULT]
Параметр	Описание	Значение по умолчанию
main_device	Имя устройства клавиатуры в Hyprland. Можно получить командой hyprctl devices -j. Значение auto — автоматическое определение первой клавиатуры.	auto
Секция [window_rules]

Задаёт правила переключения раскладки для определённых классов окон.

    Ключ — класс окна (например, Alacritty, firefox). Чтобы узнать класс активного окна, выполните hyprctl activewindow -j и посмотрите поле class.

    Значение — желаемая раскладка: us (английская) или ru (русская).

Пример:


[window_rules]
Alacritty = us
firefox = ru

Как это работает:
Скрипт отслеживает активное окно. При первом переключении на окно с правилом применяется заданная раскладка. При последующих переключениях раскладка восстанавливается из памяти (если вы меняли её вручную, она сохранится для этого окна).
Секция [auto_detect]

Настройка модуля автоматического определения транслитерации (набора русских слов в английской раскладке).
Параметр	Описание	Значение по умолчанию
enabled	Включить авто-детект. Требуется установленный evdev.	false
threshold	Минимальная длина слова для проверки (меньшие слова игнорируются).	4
notify	Показывать уведомление при обнаружении транслита. Используется notify-send.	true
auto_switch	Автоматически переключать раскладку на русскую при обнаружении транслита.	false
keyboard_device	Путь к устройству клавиатуры в /dev/input/ (например, /dev/input/event3). auto — попытка автоматического определения через evdev.	auto

Примечания:

    Для работы авто-детекта нужны права на чтение устройства клавиатуры. Обычно требуется добавить пользователя в группу input:
    bash

    sudo usermod -aG input $USER

    После этого перезайдите в систему.

    Устройство можно найти командой:
    bash

    sudo evtest

    Затем выбрать подходящее (обычно название содержит keyboard или kbd).

Логирование

Скрипт пишет лог в файл ~/.config/kb-layout-helper/helper.log. Проверяйте его при возникновении проблем.
Примеры
Только переключение по окнам

[DEFAULT]
main_device = auto

[window_rules]
Alacritty = us
firefox = ru

Только авто-детект (без правил окон)
ini

[auto_detect]
enabled = true
threshold = 3
notify = true
auto_switch = true

Полный функционал
ini

[DEFAULT]
main_device = auto

[window_rules]
Alacritty = us
firefox = ru
org.wezfurlong.wezterm = us
code = us

[auto_detect]
enabled = true
threshold = 4
notify = true
auto_switch = true
keyboard_device = /dev/input/event3

Отладка

    Проверьте, что скрипт запущен и видит вашу клавиатуру:
    bash

    tail -f ~/.config/kb-layout-helper/helper.log

    Убедитесь, что Hyprland сокет доступен:
    bash

    ls $XDG_RUNTIME_DIR/hypr/*/.socket2.sock

    Для авто-детекта проверьте права на устройство:
    bash

    ls -l /dev/input/event*

    Если ваше устройство имеет права только для root, настройте udev или добавьте пользователя в группу input.

сори за ИИ README.md но времини не хватает если что то не работает. tg : vililov / userhexov
