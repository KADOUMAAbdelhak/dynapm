FROM python:3.13.2-slim@sha256:6b3223eb4d93718828223966ad316909c39813dee3ee9395204940500792b740
WORKDIR /app
COPY dynapm/system_validation/application.py /app/dynapm/system_validation/application.py
COPY dynapm/system_validation/application_instrumented.py /app/dynapm/system_validation/application_instrumented.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
ENTRYPOINT ["python", "-m", "dynapm.system_validation.application_instrumented"]
