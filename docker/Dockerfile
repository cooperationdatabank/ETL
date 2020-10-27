FROM triply/ubuntu:20200630 as base

MAINTAINER laurens.rietveld@triply.cc

ENV TRIPLY_USER="triply" \
    TRIPLY_HOME="/home/triply" \
    TRIPLY_CACHE_DIR="/etc/docker-triply" \
    TRIPLY_LOCAL_DOCKER_ASSETS="docker"

ENV TRIPLY__PATHS__DATA_DIR="${TRIPLY_HOME}/data" \
    TRIPLY_ETL_SRC=${TRIPLY_HOME}/etl

COPY ./docker/assets/build/installWithSudo.sh /installWithSudo.sh
RUN chmod +x installWithSudo.sh && /installWithSudo.sh



RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y software-properties-common \
    && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys E298A3A825C0D65DFD57CBB651716619E084DAB9 \
    && add-apt-repository 'deb https://cloud.r-project.org/bin/linux/ubuntu bionic-cran40/' \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y  \
    jq \
    build-essential libcurl4-gnutls-dev libxml2-dev libssl-dev \
    python3-pip \
    r-base \
    && apt-get clean;

COPY ./src/loadRLibraries.R /tmp/loadRLibraries.R
RUN R -f /tmp/loadRLibraries.R

COPY ./src/requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

COPY ./docker/assets/runtime/uploadFiles-linux "${TRIPLY_HOME}/uploadFiles-linux"
RUN chmod +x "${TRIPLY_HOME}/uploadFiles-linux"

COPY ./docker/assets/runtime/runEtl "${TRIPLY_HOME}/runEtl"
RUN chmod +x "${TRIPLY_HOME}/runEtl"

COPY --chown=triply:triply ./src ${TRIPLY_ETL_SRC}

COPY ./docker/entrypoint.sh  /sbin/entrypoint.sh
RUN chmod 755 /sbin/entrypoint.sh
ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["app:run"]

VOLUME [ "${TRIPLY__PATHS__DATA_DIR}" ]
WORKDIR ${TRIPLY_ETL_SRC}
#There args all the way at the end, so they dont invalidate the cache
ARG BUILD_DATE
ARG COMMIT_SHA=''
ARG BUILD_REF=''


ENV BUILD_DATE=${BUILD_DATE} \
    COMMIT_SHA=${COMMIT_SHA} \
    BUILD_REF=${BUILD_REF}
