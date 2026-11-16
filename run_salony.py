"""Запуск сбора салонов красоты по всей Москве (двойной клик или python run_salony.py)."""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.argv = ["search.py", "салоны красоты"] + sys.argv[1:]
import search  # noqa: E402

search.main()
input("\nГотово. Нажмите Enter, чтобы закрыть.")
