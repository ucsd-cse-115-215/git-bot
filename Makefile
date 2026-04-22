PYTHON := ./venv/bin/python
FIXTURE_DIR := tmp

.PHONY: fixtures messy_solo clean-fixtures

fixtures: messy_solo

messy_solo:
	rm -rf $(FIXTURE_DIR)/messy_solo
	$(PYTHON) -m fixtures.messy_solo $(FIXTURE_DIR)/messy_solo

clean-fixtures:
	rm -rf $(FIXTURE_DIR)
