.PHONY: install dev build lint test-unit test-e2e test help

install:  ## Install dependencies
	yarn install

dev:  ## Start Next.js dev server
	yarn dev

build:  ## Production build
	yarn build

lint:  ## Run ESLint
	yarn lint

test-unit:  ## Run unit tests
	yarn jest

test-e2e:  ## Run Playwright E2E tests
	yarn playwright test

test:  ## Run all tests
	$(MAKE) test-unit
	$(MAKE) test-e2e

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
