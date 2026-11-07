.PHONY: build check serve watch clean up down logs

PY ?= python3
PORT ?= 8088

build:  ## validate the config and emit site/services.json
	$(PY) tools/build.py

check:  ## validate only, write nothing
	$(PY) tools/build.py --check

serve: build  ## build, then serve the page on :PORT (default 8088)
	@echo "  http://localhost:$(PORT)"
	@cd site && $(PY) -m http.server $(PORT)

watch:  ## rebuild whenever the config changes
	@echo "watching config/ — ctrl-c to stop"
	@while true; do \
		$(PY) tools/build.py || true; \
		sleep 2; \
	done

clean:
	rm -f site/services.json

up: build  ## build the image and start the container (needs docker)
	docker compose up -d --build

down:  ## stop and remove the container
	docker compose down

logs:  ## follow container logs
	docker compose logs -f
