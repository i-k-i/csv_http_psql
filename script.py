import sys
import os
import psycopg2
import csv
from io import StringIO
import asyncio
from aiohttp import ClientSession
import aiopg

chunk_size = 10**6

url = sys.argv[-1]

host = os.getenv('DB_HOST', 'localhost')
dbname = os.getenv('DB_NAME', 'postgres')
user = os.getenv('DB_USER', 'postgres')
password = os.getenv('DB_PASSWORD', 'postgres')

dsn = "postgres://{}:{}@{}:5432/{}".format(user, password, host, dbname)

FIELDS_TEMPLATE = '''
    id integer PRIMARY KEY,
    date date NOT NULL,
    url text NOT NULL,
    count integer NOT NULL
'''

async def fetch_data(src:dict, chunk_size:int, chunk_number:int):
    first_byte = chunk_number*chunk_size
    last_byte = chunk_number*chunk_size + chunk_size -1
    headers = {'range': 'bytes={}-{}'.format(first_byte, last_byte)}
    async with ClientSession() as session:
        async with session.get(src['url'], headers=headers) as response:
            assert response.headers['Etag'] == src['etag']
            return await response.text()

async def put_data(data:str, state:dict):
    data_size = len(data)
    data = [tuple(i) for i in csv.reader(StringIO(data))]
    async with aiopg.connect(dsn=dsn) as conn:
        async with conn.cursor() as cursor:
            records_list_template = ','.join(['%s'] * len(data))
            insert_query = 'INSERT INTO test_tmp VALUES {}'.format(records_list_template)
            await cursor.execute(insert_query, data)
            state['transfer_size'] += data_size

def cut_tails(data:str, chunk_number:int, state:dict):
    first_string, data = data.split('\r\n', 1)
    data, last_string = data.rsplit('\r\n', 1)
    state['tails'][chunk_number] = '{}\r\n{}'.format(first_string, last_string)
    return data  

async def chunk_handler(src:str, chunk_size:int, chunk_number:int, state:dict):
    print(chunk_number, src['quantity_chunks'],chunk_size, src['size'])
    data = await fetch_data(src, chunk_size, chunk_number)
    data = cut_tails(data, chunk_number, state)
    await put_data(data, state)

async def bound_handler(sem, src, chunk_size, chunk_number, state):
    async with sem:
        await chunk_handler(src, chunk_size, chunk_number, state)

async def run(url, chunk_size, dsn):
    tasks = []
    sem = asyncio.Semaphore(10)
    chunk_number = 0
    state = {'tails': {}, 'transfer_size': 0}
    src = {'url': url}

    async with ClientSession() as session:
        async with session.get(url, headers={}) as response:
            src['etag'] = response.headers['Etag']
            src['size'] = response.headers['Content-Length']
            src['quantity_chunks'] = int(src['size'])//chunk_size + 1

    async with aiopg.connect(dsn=dsn) as conn:
        async with conn.cursor() as cur:    
            await cur.execute('''
                DROP TABLE IF EXISTS test_tmp;
                CREATE TABLE test_tmp ({});
            '''.format(FIELDS_TEMPLATE))

    for chunk_number in range(src['quantity_chunks']):
        task = asyncio.ensure_future(bound_handler(sem, src, chunk_size, chunk_number, state))
        tasks.append(task)
    await asyncio.gather(*tasks)

    state['tails'] = ''.join([state['tails'][i] for i in range(len(state['tails']))])
    await put_data(state['tails'], state)

loop = asyncio.get_event_loop()
future = asyncio.ensure_future(run(url, chunk_size, dsn))
loop.run_until_complete(future)

conn = psycopg2.connect(dsn=dsn)
cur = conn.cursor()
cur.execute('''
    CREATE TABLE IF NOT EXISTS test ({});
    INSERT INTO test
    SELECT * FROM test_tmp;
    DROP TABLE test_tmp; 
'''.format(FIELDS_TEMPLATE))
conn.commit()