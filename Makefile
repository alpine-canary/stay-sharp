# Stay Sharp - common commands. Run from the repository root.
# The CDK CLI is pinned here so every machine and CI use the same version.

CDK_VERSION := 2.1147.0
CDK := npx --yes aws-cdk@$(CDK_VERSION)
PNPM := corepack pnpm
STAGE ?= dev

.PHONY: install lint typecheck test test-integration synth contract-check fault-drill canary-drill guard-not-prod

install:
	uv sync --directory api
	uv sync --directory infra
	$(PNPM) --dir front install --frozen-lockfile

lint:
	uv run --directory api ruff check .
	uv run --directory api ruff format --check .
	uv run --directory infra ruff check .
	uv run --directory infra ruff format --check .
	$(PNPM) --dir front lint

typecheck:
	uv run --directory api mypy
	uv run --directory infra mypy
	$(PNPM) --dir front typecheck

test:
	uv run --directory api pytest -m "not integration"
	uv run --directory infra pytest
	$(PNPM) --dir front test

# Needs DynamoDB Local: docker compose up -d dynamodb
test-integration:
	uv run --directory api pytest -m integration

# The API models and the front-end types must match the contract.
contract-check:
	uv run --directory api python scripts/gen_models.py
	$(PNPM) --dir front gen:api
	git diff --exit-code -- front/src/api/schema.ts

# No AWS credentials needed (committed cdk.context.json, --no-lookups).
synth:
	@if ls infra/stacks/*_stack.py >/dev/null 2>&1; then \
		cd infra && $(CDK) synth --no-lookups -q; \
	else \
		echo "synth: no stacks yet (they arrive in Phase 2); the app itself is checked by infra/tests"; \
	fi

guard-not-prod:
	@if [ "$(STAGE)" = "prod" ]; then echo "refused: drills never run against prod"; exit 1; fi

# Scenario V8 (task T081).
fault-drill: guard-not-prod
	uv run --directory api python -m tests.drills.fault_drill --stage $(STAGE)

# Scenario V9 (task T082).
canary-drill: guard-not-prod
	uv run --directory api python -m tests.drills.canary_drill --stage $(STAGE) --canary $(CANARY)
