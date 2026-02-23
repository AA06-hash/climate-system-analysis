import mysql.connector
def get_connection():
    return mysql.connector.connect(
        host="bfnpubu56egohj5zibof-mysql.services.clever-cloud.com",
        user="ugauogizjaak4q2t",
        password="0SlPPM30d4tPFebhKxTP",
        database="bfnpubu56egohj5zibof",
        port=3306
    )