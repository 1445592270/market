FROM python_base
WORKDIR /app
ADD . /app
RUN pip install --no-cache-dir --trusted-host pypi.python3.org -r requirements.txt&&pip install --no-cache-dir requests
EXPOSE 8000
CMD ["python3", "app.py"]
