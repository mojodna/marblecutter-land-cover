PATH := node_modules/.bin:$(PATH)

deploy-up: up.json deps/tiler-deps.tgz
	up

.PHONY: up.json
up.json: up.json.hbs node_modules/.bin/interp
	interp < $< > $@

node_modules/.bin/interp:
	npm install interp

deps/tiler-deps.tgz: deps/Dockerfile deps/required.txt
	docker run --rm --entrypoint tar $$(docker build --build-arg http_proxy=$(http_proxy) -t marblecutter-land-cover-tiler-deps -q -f $< .) zc -C /var/task . > $@

clean:
	rm -f deps/tiler-deps.tgz

server:
	docker build --build-arg http_proxy=$(http_proxy) -t quay.io/mojodna/marblecutter-land-cover .
