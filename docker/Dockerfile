FROM ubuntu:latest


RUN apt update && \
    apt install -y \
    tmux ripgrep git


COPY . /root/.config/tmux
WORKDIR /root/.config/tmux
RUN /root/.config/tmux/bin/tmux-init && \
    ln -s /root/.config/tmux/tmux.conf /root/.tmux.conf
