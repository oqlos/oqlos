# OqlOS — Makefile
#
# Cele lokalne (dev) i obsługa zdalnego węzła sprzętowego (Raspberry Pi, OQL-over-MQTT).
# Konfiguracja przez zmienne:
#   PI=pi@boardnet.local   host ssh węzła sprzętowego
#   NODE=122               id węzła w redeploy/ (122 = boardnet, pi-hw = 110)
#   PORT=8202              port lokalnego serwera (cel `serve`)
#
# Szybki start:  make help

PI   ?= pi@boardnet.local
NODE ?= 122
PORT ?= 8202
PYTHON ?= python

.DEFAULT_GOAL := help

.PHONY: help install-dev test test-hw smoke checksums verify-rpi sync-rpi restart \
        redeploy deploy 122 pi-hw serve panel-url

install-dev: ## Editable install: oqlos-models + oqlos-core + oqlos (monorepo)
	pip install -e packages/oqlos-models -e packages/oqlos-core -e .

help: ## Pokaż dostępne cele
	@echo "OqlOS — cele make (PI=$(PI) NODE=$(NODE))"
	@echo
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Przykłady:  make test-hw   |   make 122   |   make restart PI=pi@boardnet.local"

# --- testy ----------------------------------------------------------------
test: install-dev ## Testy jednostkowe (pytest, lokalnie)
	$(PYTHON) -m pytest -q

test-hw: ## Pełny test węzła sprzętowego na $(PI): łączność + sha256 + smoke-test
	scripts/test-hardware.sh $(PI)

smoke: ## Sam smoke-test osprzętu (assert-hw-node-healthy) na $(PI)
	@awk '/```bash markpact:ref assert-hw-node-healthy/{f=1;next} f&&/^```/{f=0} f' \
	  redeploy/$(NODE)/migration.md > /tmp/oqlos-smoke.sh
	@scp -q /tmp/oqlos-smoke.sh $(PI):/tmp/oqlos-smoke.sh
	ssh $(PI) 'export XDG_RUNTIME_DIR=/run/user/$$(id -u); bash /tmp/oqlos-smoke.sh'

# --- integralność / sync --------------------------------------------------
checksums: ## Wygeneruj manifest sha256 pakietu oqlos/ (oqlos/_CHECKSUMS.sha256)
	scripts/gen-checksums.sh

verify-rpi: ## Porównaj wdrożony pakiet oqlos/ na $(PI) z lokalnym (sha256)
	scripts/verify-rpi-checksum.sh $(PI)

sync-rpi: checksums ## Wyślij pakiet oqlos/ na $(PI) (rsync) i zweryfikuj sha256 (BEZ restartu)
	rsync -rz --itemize-changes \
	  --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.pyo' \
	  --exclude='.pytest_cache/' --exclude='*.log' \
	  oqlos/ $(PI):/home/pi/oqlos/oqlos/oqlos/
	$(MAKE) verify-rpi PI=$(PI)

restart: ## Zrestartuj agenta sprzętowego (oqlos-hardware-api) na $(PI) i sprawdź health
	ssh $(PI) 'export XDG_RUNTIME_DIR=/run/user/$$(id -u); \
	  systemctl --user restart oqlos-hardware-api; \
	  for i in $$(seq 1 20); do \
	    curl -sf --max-time 4 http://127.0.0.1:8202/health && { echo "  <- /health OK"; exit 0; }; \
	    sleep 1; \
	  done; \
	  echo "FAIL: agent nie podniosl /health w 20s" >&2; exit 1'

# --- deploy (redeploy framework) ------------------------------------------
deploy: checksums ## Pełny redeploy węzła NODE=$(NODE) (gen-checksums + redeploy run)
	redeploy run redeploy/$(NODE)/migration.md

redeploy: ## (pomoc) jak wdrożyć węzeł — użyj `make 122`, `make pi-hw` lub `make deploy NODE=...`
	@echo "Wdrożenie węzła sprzętowego:"
	@echo "  make 122                 # boardnet (192.168.188.122)"
	@echo "  make pi-hw               # pi-hw    (192.168.188.110)"
	@echo "  make deploy NODE=122     # dowolny węzeł z redeploy/<NODE>/migration.md"

122: ## Redeploy węzła boardnet (192.168.188.122)
	@$(MAKE) deploy NODE=122

pi-hw: ## Redeploy węzła pi-hw (192.168.188.110)
	@$(MAKE) deploy NODE=pi-hw PI=pi@192.168.188.110

# --- uruchamianie lokalnie -------------------------------------------------
serve: ## Uruchom serwer OqlOS lokalnie na :$(PORT) (panel pod /panel)
	$(PYTHON) -m uvicorn oqlos.api.main:app --host 0.0.0.0 --port $(PORT)

panel-url: ## Wypisz URL panelu sprzętowego
	@echo "http://localhost:$(PORT)/panel"
