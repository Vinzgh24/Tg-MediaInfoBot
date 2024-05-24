FROM ubuntu:latest

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 LANGUAGE=en_US:en TZ=Asia/Kolkata

WORKDIR /usr/src/app

RUN apt-get update -qq && apt-get upgrade -y && apt-get install -y \
    python3-pip \
    curl \
    mediainfo \
    libtinyxml2-10 \
    git \
    libcurl3-gnutls \
    libmms0 \
    libzen0v5 \
    libcurl4-gnutls-dev \
    libzen-dev \
    wget \
    ffmpeg \
    libsox-fmt-mp3 \
    sox \
    locales \
    megatools \
    python3-venv \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /usr/src/app/venv
ENV PATH="/usr/src/app/venv/bin:$PATH"

RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

COPY config.env .

RUN chmod +x start

CMD ["bash", "start"]
