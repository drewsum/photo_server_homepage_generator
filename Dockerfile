FROM ubuntu/python:3.13-25.04_stable

ADD photo_server_homepage_generator.py .

RUN pip install -r requirements.txt

CMD [“python”, “photo_server_homepage_generator.py”]