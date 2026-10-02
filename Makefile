.PHONY: play test check

PYTHON ?= python

play:
	$(PYTHON) -m tetris_trainer

test:
	$(PYTHON) -m unittest discover -s tests -v

check: test
	$(PYTHON) -m compileall -q src/tetris_trainer tests benchmarks
