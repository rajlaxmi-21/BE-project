import psycopg2

def get_connection():
    conn = psycopg2.connect(
        dbname="FinalYearProject",
        user="postgres",
        password="Shreya20",
        host="localhost",
        port="5433"   # ⚠️ IMPORTANT CHANGE
    )
    return conn
