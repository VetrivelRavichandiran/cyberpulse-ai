.PHONY: setup setup-ml setup-backend setup-frontend generate train seed demo demo-reset verify run-backend run-frontend

PY ?= python3

setup: ## Install all dependencies
	$(PY) -m pip install -r ml/requirements.txt
	$(PY) -m pip install -r backend/requirements.txt
	cd frontend && npm install

setup-ml:
	$(PY) -m pip install -r ml/requirements.txt

setup-backend:
	$(PY) -m pip install -r backend/requirements.txt

setup-frontend:
	cd frontend && npm install

generate: ## Generate synthetic dataset
	$(PY) scripts/generate_dataset.py

train: ## Train + evaluate the model
	$(PY) scripts/train_model.py

seed: ## Seed the database (demo data + users)
	$(PY) scripts/seed_database.py

demo: ## Full reproducible demo setup (data → train → seed)
	$(PY) scripts/setup_demo.py

demo-reset: ## Reset demo state
	$(PY) scripts/seed_database.py --reset

verify: ## Smoke-test the running backend (expects :8000 up + admin login)
	$(PY) scripts/verify_api.py

run-backend: ## Start the API server (dev)
	cd backend && $(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-frontend: ## Start the frontend dev server
	cd frontend && npm run dev