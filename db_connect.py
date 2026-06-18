import pymysql

def connect_db():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='invoice_system'
    )








