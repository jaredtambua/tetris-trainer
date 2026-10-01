.PHONY: play test check

play:
	python -m tetris_trainer

test:
	python -m unittest discover -s tests -v

check: test
	python -m compileall -q tetris_trainer tests
