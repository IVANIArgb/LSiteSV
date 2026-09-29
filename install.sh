#!/bin/sh
set -e
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  exec python3 ./install.py
fi
if command -v python >/dev/null 2>&1; then
  exec python ./install.py
fi
echo "Python 3 не найден. Установщик попробует поставить его сам, если запустить:"
echo "  python3 install.py"
echo "либо установите пакет python3 и повторите ./install.sh"
exit 1
