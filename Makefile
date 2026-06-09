.PHONY: build up down logs test clean migrate shell status help

help:
	@echo "Almeno Transaction Platform Commands:"
	@echo "  make build       Build the Docker containers"
	@echo "  make up          Start all services in detached mode"
	@echo "  make down        Stop all services"
	@echo "  make logs        Tail logs of all running services"
	@echo "  make test        Run unit and integration tests inside a test environment"
	@echo "  make clean       Stop services and wipe all persistent volumes"
	@echo "  make status      Check status of compose services"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose run --rm api pytest tests/

clean:
	docker compose down -v

status:
	docker compose ps
