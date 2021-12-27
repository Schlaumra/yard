init: requirements.txt
	pip install -r requirements.txt

test: tests tests/test.py
	python tests/test.py

develop: main.py
	python ./server.py

client: main.py
	python ./client.py

