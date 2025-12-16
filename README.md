1. Copy the example environment file:

```bash
cp .env.example .env.[development|staging|production] # e.g. .env.development
```

2. First time build:

```bash
docker-compose up --build
```

3. Run servers:

```bash
docker-compose up
```