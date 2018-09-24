server:
	docker build --build-arg http_proxy=$(http_proxy) -t quay.io/mojodna/marblecutter-land-cover .
