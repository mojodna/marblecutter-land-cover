FROM quay.io/mojodna/gdal:v2.3.x
LABEL maintainer="Seth Fitzsimmons <seth@mojodna.net>"

ARG http_proxy

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL C.UTF-8
ENV GDAL_CACHEMAX 512
ENV GDAL_DISABLE_READDIR_ON_OPEN TRUE
ENV GDAL_HTTP_MERGE_CONSECUTIVE_RANGES YES
ENV VSI_CACHE TRUE
# tune this according to how much memory is available
ENV VSI_CACHE_SIZE 536870912
# override this accordingly; should be 2-4x $(nproc)
ENV WEB_CONCURRENCY 4

RUN apt update \
  && apt install -y software-properties-common \
  && add-apt-repository ppa:deadsnakes/ppa \
  && apt update \
  && apt upgrade -y \
  && apt install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cython3 \
    git \
    python3.6-dev \
    python3-pip \
    python3-wheel \
    python3-setuptools \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.6 1

WORKDIR /opt/marblecutter

COPY requirements-server.txt /opt/marblecutter/
COPY requirements.txt /opt/marblecutter/

RUN pip3 install -U numpy && \
  pip3 install -r requirements-server.txt && \
  rm -rf /root/.cache

COPY landcover /opt/marblecutter/landcover

USER nobody

ENTRYPOINT ["gunicorn", "--reload", "-t", "300", "-k", "gevent", "-b", "0.0.0.0", "--access-logfile", "-", "landcover.web:app"]
