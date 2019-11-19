#!/usr/local/bin/python
import sys
import os
import psycopg2
import re

url = sys.argv[-1]

assert re.match('https?://.*', url), 'Expects url as argument'

host = os.getenv('DB_HOST', 'localhost')
dbname = os.getenv('DB_NAME', 'postgres')
user = os.getenv('DB_USER', 'postgres')
password = os.getenv('DB_PASSWORD', 'postgres')

conn = psycopg2.connect(host = host, dbname=dbname, user=user, password=password)
cursor = conn.cursor()

cursor.execute('''
    CREATE table IF NOT EXISTS test ( 
        id integer PRIMARY KEY,
        date date NOT NULL,
        url text NOT NULL,
        count integer NOT NULL);
''')
print ('Downloading datafile:')
os.system('axel -o data.csv {0}'.format(url))
print ('Copying data to db:')
with open('data.csv', 'r') as f:
    cursor.copy_from(f, 'test', sep=',')
conn.commit()
print('Done')
