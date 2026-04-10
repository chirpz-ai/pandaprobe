.PHONY: install dev build lint lint-fix typecheck format \
       test test-unit test-e2e e2e-install help

# =============================================================================
#  PandaProbe Frontend — Host-side targets
#  All commands run directly via yarn (not inside Docker).
#  Docker is only used for the dev server (make up) and production builds.
# =============================================================================

install:  ## Install dependencies
	yarn install

dev:  ## Start Next.js dev server
	yarn dev

build:  ## Production build
	yarn build

lint:  ## Run ESLint
	yarn lint

lint-fix:  ## Run ESLint with auto-fix
	yarn lint:fix

typecheck:  ## Run TypeScript type checking
	yarn typecheck

format:  ## Format code with Prettier
	yarn format

test-unit:  ## Run Jest unit tests
	yarn test

test-e2e:  ## Run Playwright E2E tests (requires e2e-install first)
	yarn test:e2e

e2e-install:  ## Download Playwright browsers (one-time setup)
	yarn playwright install --with-deps

test:  ## Run all tests (unit + E2E)
	$(MAKE) test-unit
	$(MAKE) test-e2e

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
