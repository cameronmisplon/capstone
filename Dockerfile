FROM ubuntu:20.10 AS base
RUN apt update -y
FROM base AS builder
RUN apt -y install clang-11 lldb-11 lld-11
RUN apt -y install clang
RUN apt -y install git
RUN apt update -y
RUN git clone https://github.com/JBontes/CarlSAT_2021
RUN git clone https://github.com/marijnheule/rnd-route
RUN git clone https://oauth2:bRgUGkaEAXpgvecFHLqj@gitlab.cs.uct.ac.za/capstoneproject16/capstone
RUN apt -y install make
RUN cd CarlSAT_2021; \
    make clean && make
FROM base as exec
COPY --from=builder /CarlSAT_2021/CarlSAT .
COPY --from=builder /rnd-route/tests .
COPY --from=builder /capstone .
RUN mkdir /mnt/ramdisk
RUN /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
RUN brew install mysql
RUN mysql.server start
RUN apt -y install python3 vim
RUN apt-get -y install python3-pip
RUN apt update -y
RUN pip3 install -Ur requirements.txt

