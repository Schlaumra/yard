VER = 0.0.0.1.t
CLIENTS = 2
NET = yardnet
SERVER_HOST = yardserver
PWD = $(shell pwd)
TERMINAL = terminator

init: requirements.txt
	pip install -r requirements.txt

test: source/tests source/tests
	python source/tests/test.py

develop: source/main.py
	python source/server.py

client: source/main.py
	python source/client.py

docker-build:
	rm -fR docker/client/source/*
	rm -fR docker/client/data*
	cp -R source/data source/objects source/display source/protocol source/settings source/client.py docker/client/source
	rm -fR docker/server/source/*
	rm -fR docker/server/data/*
	cp -R source/data source/objects source/display source/protocol source/settings source/server.py docker/server/source
	docker build -t yardserver:${VER} docker/server/
	docker build -t yardclient:${VER} docker/client/
	docker network rm ${NET}
	docker network create ${NET}
	${TERMINAL} -e "docker run -it --network=${NET} -v server_settings:/source/settings -v ${PWD}/docker/server/data:/source/data --hostname=${SERVER_HOST} yardserver:${VER}; echo; echo; read -p 'Press Enter to quit' temp" & sleep 1;
	for i in {1..${CLIENTS}}; do ${TERMINAL} -e "docker run -it --network=${NET} -v client_settings$$i:/source/settings -v ${PWD}/docker/client/data$$i:/source/data yardclient:${VER}; echo; echo; read -p 'Press Enter to quit' temp" & done

vm-build:
	rm -fR ../client1/*
	rm -fR ../client2/*
	cp -R ../../source/data ../../source/objects ../../source/display ../../source/protocol ../../source/settings ../../source/client.py ../client1/
	cp -R ../../source/data ../../source/objects ../../source/display ../../source/protocol ../../source/settings ../../source/client.py ../client2/
	rm -fR ./*
	cp -R ../../source/data ../../source/objects ../../source/display ../../source/protocol ../../source/settings ../../source/server.py .
	python server.py