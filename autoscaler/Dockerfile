FROM docker:cli

RUN apk add --no-cache python3 py3-requests

WORKDIR /app
COPY autoscaler.py .

CMD ["python3", "autoscaler.py"]
