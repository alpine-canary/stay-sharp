# Stay Sharp - common commands. Run from the repository root.
# The CDK CLI is pinned here so every machine and CI use the same version.

CDK_VERSION := 2.1147.0
CDK := npx --yes aws-cdk@$(CDK_VERSION)
PNPM := corepack pnpm
STAGE ?= dev

.PHONY: dkim-records ddb-download ddb-start ddb-stop install lint typecheck test test-integration synth contract-check fault-drill canary-drill guard-not-prod

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

# Needs DynamoDB Local on port 8000: `make ddb-start` (Java, no Docker) or
# `docker compose up -d dynamodb` (what CI uses).
test-integration:
	uv run --directory api pytest -m integration

# The API models and the front-end types must match the contract.
contract-check:
	uv run --directory api python scripts/gen_models.py
	uv run --directory api python scripts/gen_models.py ../specs/002-accounts/contracts/accounts.openapi.yaml staysharp.domain.accounts
	$(PNPM) --dir front gen:api
	git diff --exit-code -- front/src/api/schema.ts front/src/api/accounts-schema.ts

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

# DynamoDB Local without Docker: the official jar on a local Java (about 250 MB of memory).
# Files go to var/ (ignored by git); the archive is checked against its published SHA-256.
DDB_DIR := var/dynamodb-local
DDB_TAR := dynamodb_local_latest.tar.gz
DDB_URL := https://d1ni2b6xgvw0s0.cloudfront.net/$(DDB_TAR)
JAVA ?= $(shell if [ -x /opt/homebrew/opt/openjdk/bin/java ]; then echo /opt/homebrew/opt/openjdk/bin/java; else echo java; fi)

ddb-download:
	@test -f $(DDB_DIR)/DynamoDBLocal.jar || ( mkdir -p $(DDB_DIR) && cd $(DDB_DIR) && \
	  curl -fsSLO $(DDB_URL) && curl -fsSLO $(DDB_URL).sha256 && \
	  shasum -a 256 -c $(DDB_TAR).sha256 && tar xzf $(DDB_TAR) )

ddb-start: ddb-download
	@if [ -s $(DDB_DIR)/pid ] && kill -0 $$(cat $(DDB_DIR)/pid) 2>/dev/null; then echo "already running"; else \
	  ( cd $(DDB_DIR) || exit 1; nohup $(JAVA) -Xmx256m -Djava.library.path=./DynamoDBLocal_lib \
	    -jar DynamoDBLocal.jar -inMemory -sharedDb -port 8000 > log.txt 2>&1 & echo $$! > pid ); \
	  for i in $$(seq 40); do nc -z 127.0.0.1 8000 2>/dev/null && echo "DynamoDB Local on :8000" && exit 0; sleep 0.5; done; \
	  echo "DynamoDB Local did not start, see $(DDB_DIR)/log.txt"; exit 1; fi

ddb-stop:
	@if [ -s $(DDB_DIR)/pid ]; then kill $$(cat $(DDB_DIR)/pid) 2>/dev/null; : > $(DDB_DIR)/pid; echo stopped; fi

# The three DKIM CNAME records for the lumineth.com zone (runbook account-setup section 7).
dkim-records:
	@aws sesv2 get-email-identity --profile stay-sharp --region eu-central-2 \
		--email-identity lumineth.com \
		--query '[DkimAttributes.Status, DkimAttributes.Tokens]' --output json \
		| python3 -c 'import json,sys; status, tokens = json.load(sys.stdin); print("status:", status); [print(f"{t}._domainkey.lumineth.com CNAME {t}.dkim.amazonses.com") for t in tokens]'
