# Blue-Green Deployment Example

This folder contains a simple Docker Compose-based blue-green deployment example using Nginx.

## Components
- blue: current stable version
- green: new version candidate
- router: switches traffic between the two based on health checks and environment variables

## Start the stack
```bash
docker compose -f blue-green-deployment-comp.yml up -d
```

## Check status
```bash
docker compose -f blue-green-deployment-comp.yml ps
```

## Switch traffic
Edit the .env file and change ACTIVE_COLOR to blue or green.

```env
ACTIVE_COLOR=green
FALLBACK_COLOR=blue
```

Then recreate the router:
```bash
docker compose -f blue-green-deployment-comp.yml up -d --force-recreate router
```
