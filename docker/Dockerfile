FROM ubuntu:latest


RUN apt update && \
    apt install -y \
    tmux ripgrep git


COPY . /root/.config/tmux
WORKDIR /root/.config/tmux
RUN ln -s tmux.conf /root/.tmux.conf
