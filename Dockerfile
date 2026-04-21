# Stage check
FROM python:3.14-slim AS check

RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --break-system-packages lark "ruff~=0.14.4" "mypy~=1.19.1" "types-lxml>=2026.2.16" "pydantic~=2.12.5" "pydantic-xml[lxml]~=2.19.0"

WORKDIR /src
ENTRYPOINT [ "/bin/bash" ]

# Stage build (interpreter)
FROM python:3.14-slim AS build
WORKDIR /app/int
COPY int/ ./

# Stage build-test (tester)
FROM node:24-bookworm-slim AS build-test
WORKDIR /app/tester

COPY tester/package*.json ./
COPY tester/tsconfig.json ./
RUN npm install

COPY tester/ ./
RUN npm run build

# runtime
FROM python:3.14-slim AS runtime
WORKDIR /app

RUN pip install --no-cache-dir lark "pydantic~=2.12.5" "pydantic-xml[lxml]~=2.19.0"

# copy content from build stage
COPY --from=build /app/int ./int

ENTRYPOINT [ "python3", "int/src/solint.py" ]

# test stage
FROM runtime AS test
RUN apt-get update && apt-get install -y \
    nodejs \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY --from=build-test /app/tester/dist ./tester/dist
COPY --from=build-test /app/tester/node_modules ./tester/node_modules

ENTRYPOINT [ "node", "tester/dist/tester.js" ]
