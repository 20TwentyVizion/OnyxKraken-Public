# OnyxKraken — Common Commands
# Usage: make <target>

.PHONY: help install test lint serve face demo clean

help: ## Show this help
	@findstr /R "^[a-zA-Z_-]*:.*##" Makefile

install: ## Install all dependencies
	pip install -r requirements.txt

test: ## Run test suite
	pytest tests/ -x --timeout=60 -q --tb=short

lint: ## Run linter (ruff)
	ruff check --select=E9,F63,F7,F82 .

serve: ## Start FastAPI server on port 8420
	uvicorn server:app --host 0.0.0.0 --port 8420 --reload

face: ## Launch Face GUI
	python main.py

studio: ## Launch Animation Studio
	python main.py studio

demo: ## Run default demo sequence
	python main.py demo hello

clean: ## Remove __pycache__, .pyc, .pytest_cache
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
	for /d /r . %%d in (.pytest_cache) do @if exist "%%d" rd /s /q "%%d"
	del /s /q *.pyc 2>nul
