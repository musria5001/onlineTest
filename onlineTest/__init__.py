import pymysql
pymysql.install_as_MySQLdb()

from .settings import USER_FILE_DIR, LOG_DIR
import os

def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


_ensure_dir(USER_FILE_DIR)
_ensure_dir(os.path.join(USER_FILE_DIR, "allCode"))
_ensure_dir(os.path.join(USER_FILE_DIR, "codeWeekTarFiles"))
_ensure_dir(os.path.join(USER_FILE_DIR, "codeZip"))
_ensure_dir(os.path.join(USER_FILE_DIR, "reportFile"))
_ensure_dir(os.path.join(USER_FILE_DIR, "upload"))
_ensure_dir(LOG_DIR)
