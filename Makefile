.PHONY: start stop test build

start:
	powershell -ExecutionPolicy Bypass -File start-northstar.ps1

stop:
	powershell -ExecutionPolicy Bypass -File stop-northstar.ps1

test:
	backend/.venv/Scripts/python.exe -m pytest backend/tests -q

build:
	cd frontend && npm run build
