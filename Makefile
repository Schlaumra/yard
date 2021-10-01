init: requirements.txt
	pip install -r requirements.txt

test: tests tests/test.py
	python tests/test.py

develop: main.py
	python main.py

