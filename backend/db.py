import psycopg2

def get_connection():
    conn = psycopg2.connect(
    dbname="FinalYearProject",
    user="rajlaxmiawatade",
    host="localhost",
    port="5432"
    )
    return conn
