FROM ubuntu:latest


RUN apt update && \
    apt install -y \
    ripgrep git


COPY . /_install
RUN /_install/bin/tmux-init
