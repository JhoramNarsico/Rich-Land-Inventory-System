# core/__init__.py

import pymysql

# This line tells Django to use PyMySQL
pymysql.install_as_MySQLdb()

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
