FROM python:3.7.0-alpine

RUN apk update && apk add axel
RUN apk update && apk add libpq
RUN apk update && apk add --virtual .build-deps gcc python3-dev musl-dev postgresql-dev


RUN mkdir -p /data/db_filler
WORKDIR /data/db_filler
COPY script.py /usr/local/bin/
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

RUN apk del .build-deps