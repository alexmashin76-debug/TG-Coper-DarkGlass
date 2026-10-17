#!/usr/bin/env bash
# TG_Coper resilient launcher for Kali/Debian and file-manager launches.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR"
LOG="$SCRIPT_DIR/startup_error.log"
APP="tg_coper_panel.py"
REQ="requirements.txt"

# Keep a complete trace even if a terminal window closes after a file-manager launch.
: > "$LOG"
if command -v tee >/dev/null 2>&1; then
  exec > >(tee -a "$LOG") 2>&1
else
  exec >> "$LOG" 2>&1
fi

say() { printf '[TG_Coper %s] %s\n' "$(date '+%F %T')" "$*"; }
notify_failure() {
  local msg="TG_Coper не запустился. Подробности сохранены в: $LOG"
  say "ОШИБКА: $*"
  if [[ -t 0 ]]; then
    printf '\n%s\nНажмите Enter, чтобы закрыть это окно...' "$msg"
    read -r _ || true
  elif command -v zenity >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    zenity --error --title='TG_Coper — ошибка запуска' --text="$msg" 2>/dev/null || true
  fi
  exit 1
}
trap 'rc=$?; say "Необработанная ошибка в строке ${LINENO} (код $rc). Смотрите startup_error.log."; if [[ -t 0 ]]; then printf "\nНажмите Enter, чтобы закрыть окно..."; read -r _ || true; fi; exit "$rc"' ERR

[[ -f "$APP" ]] || notify_failure "Не найден файл $APP в $SCRIPT_DIR"
[[ -f "$REQ" ]] || notify_failure "Не найден файл $REQ в $SCRIPT_DIR"

# System package installation is limited to Kali/Debian; sudo may ask for the OS password.
apt_install() {
  local packages=("$@")
  command -v apt-get >/dev/null 2>&1 || notify_failure "Для установки ${packages[*]} нужен apt-get (Kali/Debian)."
  if [[ $EUID -eq 0 ]]; then
    say "Обновляю список пакетов и устанавливаю: ${packages[*]}"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
  elif command -v sudo >/dev/null 2>&1; then
    say "Нужна системная установка: ${packages[*]}. Может появиться запрос пароля sudo."
    sudo -v
    sudo apt-get update
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
  else
    notify_failure "Нет root/sudo для установки системных пакетов: ${packages[*]}"
  fi
}

if ! command -v python3 >/dev/null 2>&1; then
  say "Python 3 не найден. Пытаюсь установить Python 3 и компоненты запуска автоматически."
  apt_install python3 python3-venv python3-pip python3-tk
fi
command -v python3 >/dev/null 2>&1 || notify_failure "Python 3 всё ещё недоступен после установки."

if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  say "Tkinter отсутствует; пытаюсь установить системный пакет python3-tk."
  apt_install python3-tk
fi
python3 -c 'import tkinter' >/dev/null 2>&1 || notify_failure "Не удалось импортировать tkinter. Проверьте startup_error.log."

# Prefer system packages if complete; otherwise create an isolated environment that can see system packages.
if python3 -c 'import PIL, telethon' >/dev/null 2>&1; then
  PY="$(command -v python3)"
  say "Использую системный Python и уже установленные Pillow/Telethon/Tkinter."
else
  VENV="$SCRIPT_DIR/.venv"
  PY="$VENV/bin/python"
  if [[ ! -x "$PY" ]] || ! "$PY" -c 'import sys; assert sys.version_info.major == 3' >/dev/null 2>&1; then
    say "Подготавливаю локальное окружение Python с доступом к системным библиотекам."
    if ! python3 -m venv --system-site-packages "$VENV"; then
      say "Создание venv не удалось; устанавливаю компоненты python3-venv и python3-pip."
      apt_install python3-venv python3-pip
      python3 -m venv --system-site-packages "$VENV" || notify_failure "Не удалось создать .venv даже после установки python3-venv."
    fi
  fi
  if ! "$PY" -c 'import PIL, telethon' >/dev/null 2>&1; then
    say "Устанавливаю недостающие зависимости из requirements.txt в .venv."
    "$PY" -m pip install --upgrade pip
    "$PY" -m pip install -r "$REQ"
  fi
fi

"$PY" -c 'import tkinter, PIL, telethon' || notify_failure "Проверка зависимостей не пройдена. Полный вывод выше и в startup_error.log."
say "Проверка зависимостей пройдена. Запускаю приложение: $APP"
set +e
"$PY" -u "$APP"
rc=$?
set -e
if (( rc != 0 )); then
  notify_failure "Приложение завершилось с кодом $rc. Смотрите traceback выше и startup_error.log."
fi
say "Приложение завершено без кода ошибки."
