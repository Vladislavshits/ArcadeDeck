#!/bin/bash

# Проверка наличия zenity
if ! command -v zenity &> /dev/null; then
    echo "Для работы установщика требуется zenity. Установите его командой:"
    echo "sudo apt install zenity"
    exit 1
fi

# Определение домашней директории пользователя
USER_HOME="$HOME"
APP_NAME="PixelDeck"
INSTALL_DIR="$USER_HOME/$APP_NAME"
DESKTOP_FILE="$USER_HOME/.local/share/applications/$APP_NAME.desktop"
DESKTOP_SHORTCUT="$USER_HOME/Desktop/$APP_NAME.desktop"  # Ярлык на рабочем столе
LOG_FILE="$INSTALL_DIR/install.log"
CRASH_FILE="$INSTALL_DIR/crash.txt"
INSTALLER_PATH="$0"

# URL репозитория GitHub
GITHUB_REPO="https://github.com/Vladislavshits/PixelDeck"
RAW_GITHUB_URL="https://raw.githubusercontent.com/Vladislavshits/PixelDeck/main"

# Функция для записи логов
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Функция проверки успешности выполнения команды
check_success() {
    if [ $? -ne 0 ]; then
        log "ОШИБКА: $1"
        echo "ОШИБКА: $1" >> "$CRASH_FILE"
        echo "Подробности в логах: $LOG_FILE" >> "$CRASH_FILE"
        zenity --error --width=500 --text="Ошибка на шаге:\n$1\n\nПодробности в файле $CRASH_FILE"
        exit 1
    fi
}

# Функция проверки интернет-соединения
check_internet() {
    if ! ping -c 1 -W 2 raw.githubusercontent.com &> /dev/null; then
        if ! ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
            zenity --error --width=400 --text="Требуется интернет-соединение для установки PixelDeck!\n\nПожалуйста, подключитесь к интернету и повторите попытку."
            exit 1
        fi
    fi
}

# Функция для загрузки файла с GitHub
download_from_github() {
    local file_name="$1"
    local dest_path="$2"

    log "Загрузка $file_name с GitHub..."
    if command -v wget &> /dev/null; then
        wget -q "$RAW_GITHUB_URL/$file_name" -O "$dest_path"
    elif command -v curl &> /dev/null; then
        curl -sL "$RAW_GITHUB_URL/$file_name" -o "$dest_path"
    else
        log "Не найдены wget или curl для загрузки файлов"
        return 1
    fi

    if [ ! -f "$dest_path" ]; then
        log "Файл $file_name не был загружен"
        return 1
    fi

    return 0
}

# Проверка интернета перед началом установки
check_internet

# Обновлённый текст установки
response=$(zenity --question \
  --title="Добро пожаловать в PixelDeck!" \
  --text="Эта программа, созданная на основе моих гайдов, призвана упростить эмуляцию на Steam Deck.\n\nВ дальнейшем эта программа получит функции автоустановки эмуляторов, их настройки, а так же авто-скачивание игр.\n\nХотите ли вы установить программу?" \
  --ok-label="Установить" \
  --cancel-label="Отмена" \
  --width=500)

if [ $? -ne 0 ]; then
    zenity --info --width=300 --text="Установка отменена"
    exit 0
fi

# Создаем директорию для приложения
mkdir -p "$INSTALL_DIR"
touch "$LOG_FILE"
chmod 600 "$LOG_FILE"

# Прогресс установки с задержками
(
    # Шаг 1/11: Создание директории
    echo "10"
    echo "# Создание директории приложения..."
    log "Создание директории $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    check_success "Создание директории $INSTALL_DIR"
    sleep 0.5

    # Шаг 2/11: Загрузка основного файла программы
    echo "20"
    echo "# Загрузка программы с GitHub..."
    download_from_github "PixelDeck.py" "$INSTALL_DIR/PixelDeck.py"
    check_success "Загрузка PixelDeck.py"
    sleep 0.5

    # Шаг 3/11: Загрузка файла guides.json
    echo "30"
    echo "# Загрузка списка гайдов с GitHub..."
    download_from_github "guides.json" "$INSTALL_DIR/guides.json"
    check_success "Загрузка guides.json"
    sleep 0.5

    # Шаг 4/11: Создание папки стилей
    echo "40"
    echo "# Создание папки стилей..."
    STYLES_DIR="$INSTALL_DIR/data/style"
    mkdir -p "$STYLES_DIR"
    check_success "Создание папки стилей"
    log "Папка стилей создана: $STYLES_DIR"
    sleep 0.5

    # Шаг 5/11: Загрузка файлов стилей
    STYLE_FILES=(
        "main_window_dark.qss"
        "main_window_light.qss"
        "welcome_dialog_dark.qss"
        "welcome_dialog_light.qss"
        "settings_dialog_dark.qss"
        "settings_dialog_light.qss"
    )

    total_files=${#STYLE_FILES[@]}
    current_file=0

    for style_file in "${STYLE_FILES[@]}"; do
        current_file=$((current_file + 1))
        progress=$((40 + current_file * 5))

        echo "$progress"
        echo "# Загрузка стиля ($current_file/$total_files): $style_file..."
        log "Начало загрузки стиля: $style_file"

        download_from_github "data/style/$style_file" "$STYLES_DIR/$style_file"

        # Проверяем результат загрузки
        if [ $? -ne 0 ]; then
            log "Ошибка: не удалось загрузить файл стиля $style_file"
            zenity --warning --text="Не удалось загрузить файл стиля $style_file" --width=300
        else
            log "Файл стиля $style_file успешно загружен"
        fi

        sleep 0.2
    done

    # Шаг 6/11: Загрузка иконки
    echo "70"
    echo "# Загрузка иконки приложения..."
    log "Начало загрузки иконки"
    download_from_github "icon.png" "$INSTALL_DIR/icon.png"
    # Не критичная ошибка, если иконка не загрузится
    if [ $? -ne 0 ]; then
        log "Предупреждение: не удалось загрузить иконку"
    else
        log "Иконка успешно загружена"
    fi
    sleep 0.5

    # Шаг 7/11: Установка прав
    echo "75"
    echo "# Установка прав доступа..."
    log "Установка прав на исполнение для PixelDeck.py"
    chmod +x "$INSTALL_DIR/PixelDeck.py"
    check_success "Установка прав на исполнение"
    sleep 0.5

    # Шаг 8/11: Проверка зависимостей
    echo "80"
    echo "# Проверка зависимостей..."

    # Проверка Python
    if ! command -v python3 &> /dev/null; then
        log "Python3 не установлен, начинаем установку"
        sudo apt update
        sudo apt install -y python3
        check_success "Установка Python3"
        log "Python3 успешно установлен"
    else
        log "Python3 уже установлен"
    fi
    sleep 0.5

    # Проверка pip
    echo "85"
    echo "# Установка pip3..."
    if ! command -v pip3 &> /dev/null; then
        log "pip3 не установлен, начинаем установку"
        sudo apt install -y python3-pip
        check_success "Установка pip3"
        log "pip3 успешно установлен"
    else
        log "pip3 уже установлен"
    fi
    sleep 0.5

    # Проверка PyQt5
    echo "90"
    echo "# Установка PyQt5..."
    if ! python3 -c "import PyQt5" &> /dev/null; then
        log "PyQt5 не установлен, начинаем установку"
        pip3 install PyQt5
        check_success "Установка PyQt5"
        log "PyQt5 успешно установлен"
    else
        log "PyQt5 уже установлен"
    fi
    sleep 0.5

    # Шаг 9/11: Создание ярлыков
    echo "95"
    echo "# Создание ярлыков приложения..."
    log "Создание ярлыков..."

    # Проверяем, есть ли иконка
    ICON_PATH="applications-games"
    if [ -f "$INSTALL_DIR/icon.png" ]; then
        ICON_PATH="$INSTALL_DIR/icon.png"
    fi

    # Создаем директории для ярлыков
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    mkdir -p "$(dirname "$DESKTOP_SHORTCUT")"

    # Ярлык для меню приложений
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=PixelDeck
Comment=Установка и настройка эмуляторов на Steam Deck
Exec=python3 $INSTALL_DIR/PixelDeck.py
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Game;Utility;
Keywords=emulator;steam;deck;guide;
EOF
    check_success "Создание .desktop файла (меню)"
    log "Ярлык для меню приложений создан"

    # Ярлык на рабочем столе
    cat > "$DESKTOP_SHORTCUT" <<EOF
[Desktop Entry]
Name=PixelDeck
Comment=Установка и настройка эмуляторов на Steam Deck
Exec=python3 $INSTALL_DIR/PixelDeck.py
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Game;Utility;
Keywords=emulator;steam;deck;guide;
EOF
    chmod +x "$DESKTOP_SHORTCUT"  # Делаем ярлык на рабочем столе запускаемым
    check_success "Создание .desktop файла (рабочий стол)"
    log "Ярлык на рабочем столе создан"
    sleep 0.5

    # Шаг 10/11: Обновление меню
    echo "98"
    echo "# Обновление меню приложений..."
    log "Обновление меню приложений"
    update-desktop-database "$USER_HOME/.local/share/applications"
    check_success "Обновление меню приложений"
    sleep 0.5

    # Шаг 11/11: Завершение установки
    echo "100"
    echo "# Завершение установки..."
    log "Установка успешно завершена"
    sleep 0.5

) | zenity --progress \
  --title="Установка $APP_NAME" \
  --text="Подготовка к установке..." \
  --percentage=0 \
  --auto-close \
  --width=400 \
  --height=120  # Увеличенная высота окна

# Проверка статуса завершения установки
if [ "$?" = -1 ]; then
    log "Установка прервана пользователем"
    zenity --error --text="Установка прервана"
    exit 1
fi

# Создание скрипта удаления
UNINSTALLER="$INSTALL_DIR/uninstall.sh"
log "Создание скрипта удаления"
cat > "$UNINSTALLER" <<EOF
#!/bin/bash
# Запрос подтверждения
if zenity --question --text="Вы уверены, что хотите удалить $APP_NAME?"; then
    # Удаление папки приложения
    rm -rf "$INSTALL_DIR"
    # Удаление .desktop файлов
    rm -f "$DESKTOP_FILE"
    rm -f "$DESKTOP_SHORTCUT"
    # Обновление меню
    update-desktop-database "$USER_HOME/.local/share/applications"
    zenity --info --text="Программа $APP_NAME была удалена."
else
    zenity --info --text="Удаление отменено."
fi
EOF
chmod +x "$UNINSTALLER"
log "Скрипт удаления создан: $UNINSTALLER"

# Удаляем crash.txt если он пустой или не создавался
if [ -f "$CRASH_FILE" ] && [ ! -s "$CRASH_FILE" ]; then
    rm -f "$CRASH_FILE"
fi

# Финальное сообщение с кнопками запуска
response=$(zenity --question \
  --title="PixelDeck успешно установлен!" \
  --text="<b>PixelDeck успешно установлен!</b>\n\nПрограмму можно запустить:\n- С рабочего стола (ярлык PixelDeck)\n- Из меню приложений (поиск \"PixelDeck\")\n\nДля удаления программы используйте файл uninstall.sh в папке приложения.\n\nЗапустить программу сейчас?" \
  --ok-label="Запустить сейчас" \
  --cancel-label="Закрыть" \
  --width=500 \
  --extra-button="Открыть папку" \
  --window-icon=info)

ret=$?

if [ $ret -eq 0 ]; then
    # Запуск приложения
    log "Запуск приложения"
    python3 "$INSTALL_DIR/PixelDeck.py" &
elif [ "$response" = "Открыть папку" ]; then
    # Открытие папки с программой
    log "Открытие папки приложения"
    xdg-open "$INSTALL_DIR"
fi
