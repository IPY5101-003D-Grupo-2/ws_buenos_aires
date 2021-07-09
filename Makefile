
NOMBRE_APP=ws-buenos-aires

.DEFAULT_GOAL := all

build:
		heroku container:push web -a=${NOMBRE_APP}

push:
		heroku container:release web -a=${NOMBRE_APP}

all: build push 