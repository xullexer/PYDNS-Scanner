"""
PyInstaller hook for Rich library to include all Unicode data files
"""

from PyInstaller.utils.hooks import collect_data_files

# Collect all data files from rich package including unicode data
datas = collect_data_files("rich", include_py_files=True)
