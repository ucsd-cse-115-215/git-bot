PYTHON := ./venv/bin/python
INSPECT := ./venv/bin/inspect
FIXTURE_DIR := tmp
MODEL ?= openai/gpt-5-mini
# Which agent the Inspect eval should target: "dsl" (v1 typed tools)
# or "shell" (v0.x bash tool). Override with `make ... AGENT=shell`.
AGENT ?= dsl

.PHONY: fixtures messy_solo clean-fixtures inspect-smoke inspect-eval inspect-view test

fixtures: messy_solo

messy_solo:
	rm -rf $(FIXTURE_DIR)/messy_solo
	$(PYTHON) -m fixtures.messy_solo $(FIXTURE_DIR)/messy_solo

clean-fixtures:
	rm -rf $(FIXTURE_DIR)

# One scenario, full epoch count from task definition. Cheap smoke test.
inspect-smoke:
	PYTHONPATH=. $(INSPECT) eval evals/inspect_task.py --model $(MODEL) --limit 1 -T agent=$(AGENT)

# Full eval: all scenarios, full epoch count from task definition.
inspect-eval:
	PYTHONPATH=. $(INSPECT) eval evals/inspect_task.py --model $(MODEL) -T agent=$(AGENT)

inspect-view:
	$(INSPECT) view --log-dir logs

# Gold-trajectory tests for the git DSL: each eval scenario gets a
# hand-written sequence of DSL calls and we assert the oracle passes.
test:
	PYTHONPATH=. $(PYTHON) -m unittest tests.test_dsl_scenarios -v
