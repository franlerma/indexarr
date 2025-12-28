.PHONY: up down test restart logs clean rebuild install help

# Variables
COMPOSE_FILE = docker-compose.yml
SERVICE_NAME = indexerr

help:
	@echo "Makefile for Indexarr"
	@echo ""
	@echo "Available commands:"
	@echo "  make up        - Start container (without rebuild)"
	@echo "  make test      - Full rebuild and start container"
	@echo "  make down      - Stop and remove container"
	@echo "  make restart   - Restart container"
	@echo "  make logs      - View container logs"
	@echo "  make clean     - Clean everything (container + image)"
	@echo "  make rebuild   - Clean and rebuild from scratch"
	@echo "  make install   - Install dependencies locally"

up:
	@echo "Stopping container if exists..."
	docker-compose down 2>/dev/null || true
	@echo "Starting container..."
	docker-compose up -d
	@echo "✓ Container started at http://localhost:15505"

test:
	@echo "Stopping container if exists..."
	docker-compose down 2>/dev/null || true
	@echo "Removing previous image..."
	docker rmi $(SERVICE_NAME):latest 2>/dev/null || true
	@echo "Building new image from scratch..."
	docker-compose build --no-cache
	@echo "Starting container..."
	docker-compose up -d
	@echo "✓ Test container started at http://localhost:15505"

down:
	@echo "Stopping container..."
	docker-compose down
	@echo "✓ Container stopped"

restart:
	@echo "Restarting container..."
	docker-compose restart
	@echo "✓ Container restarted"

logs:
	docker-compose logs -f

clean:
	@echo "Cleaning everything..."
	docker-compose down -v
	docker rmi $(SERVICE_NAME):latest 2>/dev/null || true
	@echo "✓ Cleanup completed"

rebuild: clean up

install:
	@echo "Installing dependencies..."
	pip install --break-system-packages -r requirements.txt
	@echo "✓ Dependencies installed"
