import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="DbmS@142@DbmS",   # your actual password
        database="climate_research"
    )