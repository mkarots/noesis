# Deploying Your Noesis Agents

This guide covers deploying agents you've built with the Noesis framework to production environments.

## Prerequisites

- A Noesis agent application
- Docker installed (for containerized deployment)
- Basic understanding of Python deployment

## Project Structure

Your agent project should look like this:

```
my-agent/
├── agent.py           # Your agent implementation
├── requirements.txt   # Dependencies (includes noesis)
├── Dockerfile         # Docker configuration
├── docker-compose.yml # Optional: for local testing
└── .env              # Environment variables (not committed)
```

## Step 1: Create Your Agent

Create your agent implementation (`agent.py`):

```python
from noesis import Agent, InMemoryStore
from noesis.http import build_fastapi
from noesis.middleware import timeout_middleware, session_middleware

# Initialize your agent
agent = Agent(
    name="my_production_agent",
    description="My custom agent for production"
)

# Configure memory (optional)
memory = InMemoryStore()
agent.use_memory(memory)

# Add middlewares
agent.use(timeout_middleware(30.0))
agent.use(session_middleware())

# Define your tools
@agent.tool
async def my_custom_tool(data: str) -> str:
    """Your custom business logic."""
    # Process data
    return f"Processed: {data}"

# Define your handler
@agent.handler
async def handle(ctx):
    """Main agent logic."""
    action = ctx.input.get("action")
    
    if action == "process":
        data = ctx.input.get("data")
        result = await ctx.tool("my_custom_tool", data=data)
        return {"result": result, "status": "success"}
    
    return {"error": "Unknown action"}

# Create FastAPI app for HTTP deployment
app = build_fastapi(agent)
```

## Step 2: Define Dependencies

Create `requirements.txt`:

```txt
# Core framework
noesis>=0.1.0

# Web server
uvicorn[standard]>=0.24.0

# Optional: Add your custom dependencies
# requests>=2.31.0
# sqlalchemy>=2.0.0
# redis>=5.0.0
```

Or use `pyproject.toml`:

```toml
[project]
name = "my-agent"
version = "0.1.0"
dependencies = [
    "noesis>=0.1.0",
    "uvicorn[standard]>=0.24.0",
]
```

## Step 3: Create Dockerfile

**Simple Dockerfile** (recommended for getting started):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your agent code
COPY agent.py .

# Expose port
EXPOSE 8000

# Run the agent
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Production Dockerfile** (optimized):

```dockerfile
# Build stage
FROM python:3.12-slim as builder

WORKDIR /build

# Install dependencies in a virtual environment
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY agent.py .

# Use the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 agent && \
    chown -R agent:agent /app
USER agent

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run with multiple workers for production
CMD ["uvicorn", "agent:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4"]
```

## Step 4: Build and Run Locally

### Build the image:

```bash
docker build -t my-agent:latest .
```

### Run the container:

```bash
# Simple run
docker run -p 8000:8000 my-agent:latest

# With environment variables
docker run -p 8000:8000 \
  -e LOG_LEVEL=info \
  -e API_KEY=your-secret-key \
  my-agent:latest

# With volume for hot-reload during development
docker run -p 8000:8000 \
  -v $(pwd)/agent.py:/app/agent.py \
  my-agent:latest
```

### Test your agent:

```bash
# Health check
curl http://localhost:8000/health

# Invoke the agent
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "action": "process",
      "data": "test data"
    }
  }'
```

## Step 5: Docker Compose for Development

Create `docker-compose.yml` for easier local development:

```yaml
version: '3.8'

services:
  agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=debug
    volumes:
      # Hot reload during development
      - ./agent.py:/app/agent.py
    restart: unless-stopped

  # Optional: Add Redis for distributed memory
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped
```

Run with:

```bash
docker-compose up
```

## Deployment Platforms

### Option 1: AWS (Recommended)

#### AWS Elastic Container Service (ECS)

1. **Push to ECR:**

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

# Create repository
aws ecr create-repository --repository-name my-agent

# Tag and push
docker tag my-agent:latest <account>.dkr.ecr.us-east-1.amazonaws.com/my-agent:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/my-agent:latest
```

2. **Create ECS Task Definition (task-definition.json):**

```json
{
  "family": "my-agent",
  "containerDefinitions": [
    {
      "name": "my-agent",
      "image": "<account>.dkr.ecr.us-east-1.amazonaws.com/my-agent:latest",
      "memory": 512,
      "cpu": 256,
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "LOG_LEVEL", "value": "info"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/my-agent",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "networkMode": "awsvpc",
  "memory": "512",
  "cpu": "256"
}
```

3. **Deploy:**

```bash
aws ecs create-service \
  --cluster my-cluster \
  --service-name my-agent \
  --task-definition my-agent \
  --desired-count 2 \
  --launch-type FARGATE
```

### Option 2: Google Cloud Run

Simple deployment with automatic scaling:

```bash
# Build and submit
gcloud builds submit --tag gcr.io/PROJECT_ID/my-agent

# Deploy
gcloud run deploy my-agent \
  --image gcr.io/PROJECT_ID/my-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 512Mi
```

### Option 3: Azure Container Instances

```bash
# Login to Azure
az login

# Create resource group
az group create --name my-agent-rg --location eastus

# Deploy container
az container create \
  --resource-group my-agent-rg \
  --name my-agent \
  --image your-registry.azurecr.io/my-agent:latest \
  --cpu 1 \
  --memory 1 \
  --registry-login-server your-registry.azurecr.io \
  --registry-username <username> \
  --registry-password <password> \
  --dns-name-label my-agent \
  --ports 8000
```

### Option 4: Kubernetes

Create deployment files:

**deployment.yaml:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-agent
  template:
    metadata:
      labels:
        app: my-agent
    spec:
      containers:
      - name: my-agent
        image: my-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: LOG_LEVEL
          value: "info"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: my-agent-service
spec:
  selector:
    app: my-agent
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

Deploy:

```bash
kubectl apply -f deployment.yaml
```

### Option 5: Simple VPS/VM Deployment

For a simple VPS (DigitalOcean, Linode, etc.):

```bash
# On your server
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Pull and run your agent
docker run -d \
  --name my-agent \
  --restart unless-stopped \
  -p 80:8000 \
  my-agent:latest

# Optional: Use nginx as reverse proxy
# Install nginx and configure SSL with Let's Encrypt
```

## Environment Variables & Configuration

### Managing Secrets

**Never hardcode secrets!** Use environment variables:

```python
import os

# agent.py
API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
```

### .env File (for local development only):

```bash
# .env
LOG_LEVEL=debug
API_KEY=dev-key-123
DATABASE_URL=postgresql://localhost/mydb
REDIS_URL=redis://localhost:6379
```

Add to `.gitignore`:

```
.env
```

### Production Secrets

Use your platform's secret management:

- **AWS:** AWS Secrets Manager or Parameter Store
- **GCP:** Secret Manager
- **Azure:** Key Vault
- **Kubernetes:** Secrets

Example with AWS Secrets Manager:

```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

secrets = get_secret('my-agent/prod')
API_KEY = secrets['api_key']
```

## Monitoring & Logging

### Add Structured Logging

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
        }
        return json.dumps(log_entry)

# Configure in agent.py
logging.basicConfig(level=logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.root.handlers = [handler]
```

### Add Health Checks

The built-in `/health` endpoint is included automatically. For custom health checks:

```python
from fastapi import Response

@app.get("/health/detailed")
async def detailed_health():
    """Detailed health check with dependencies."""
    checks = {
        "status": "healthy",
        "database": await check_database(),
        "redis": await check_redis(),
    }
    
    if all(checks.values()):
        return checks
    else:
        return Response(content=json.dumps(checks), status_code=503)
```

### Add Metrics (Optional)

```python
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

# Define metrics
request_count = Counter('agent_requests_total', 'Total requests')
request_duration = Histogram('agent_request_duration_seconds', 'Request duration')

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")
```

## Performance & Scaling

### Horizontal Scaling

Run multiple instances behind a load balancer:

```bash
# Docker Compose
docker-compose up --scale agent=3
```

### Vertical Scaling

Increase resources in your Dockerfile:

```bash
CMD ["uvicorn", "agent:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \  # Increase workers
     "--limit-concurrency", "100"]
```

### Use Production Web Server

For high-performance production:

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
CMD ["gunicorn", "agent:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", \
     "-b", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

## Troubleshooting

### View Logs

```bash
# Docker
docker logs my-agent

# Docker Compose
docker-compose logs -f agent

# Kubernetes
kubectl logs -f deployment/my-agent
```

### Debug in Container

```bash
docker exec -it my-agent /bin/bash
```

### Common Issues

**Port already in use:**
```bash
# Change the port mapping
docker run -p 8080:8000 my-agent:latest
```

**Memory issues:**
```bash
# Increase memory limit
docker run --memory="512m" my-agent:latest
```

**Connection refused:**
- Check if the app is binding to `0.0.0.0`, not `127.0.0.1`
- Verify firewall rules
- Check health endpoint: `curl http://localhost:8000/health`

## Continuous Deployment

### GitHub Actions Example

`.github/workflows/deploy.yml`:

```yaml
name: Deploy Agent

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to Amazon ECR
        run: |
          aws ecr get-login-password | docker login --username AWS \
            --password-stdin ${{ secrets.ECR_REGISTRY }}
      
      - name: Build and push
        run: |
          docker build -t my-agent:${{ github.sha }} .
          docker tag my-agent:${{ github.sha }} ${{ secrets.ECR_REGISTRY }}/my-agent:latest
          docker push ${{ secrets.ECR_REGISTRY }}/my-agent:latest
      
      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster my-cluster \
            --service my-agent --force-new-deployment
```

## Best Practices Checklist

- [ ] Use environment variables for configuration
- [ ] Never commit secrets to Git
- [ ] Implement proper error handling
- [ ] Add health checks
- [ ] Enable structured logging
- [ ] Set resource limits
- [ ] Use multi-stage builds for smaller images
- [ ] Run as non-root user
- [ ] Add rate limiting for public endpoints
- [ ] Enable HTTPS in production
- [ ] Monitor your agent's performance
- [ ] Set up alerting for failures
- [ ] Have a rollback strategy
- [ ] Document your API endpoints

## Next Steps

1. Test your agent locally with Docker
2. Set up CI/CD pipeline
3. Deploy to staging environment
4. Load test your agent
5. Deploy to production
6. Monitor and iterate

For more examples, see the `examples/` directory in the Noesis repository.
