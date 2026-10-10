FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py wsgi.py run_production.py backup.py /app/
COPY static /app/static
RUN useradd --create-home ssms && mkdir /app/data && chown -R ssms:ssms /app
USER ssms
ENV SSMS_DB=/app/data/ssms.sqlite3 SSMS_ENV=production SSMS_SECURE_COOKIES=1 SSMS_HOST=0.0.0.0
EXPOSE 8000
CMD ["python", "run_production.py"]
