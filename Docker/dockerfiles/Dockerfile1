FROM ubuntu:22.04

WORKDIR /usr/src/app

RUN <<EOF 
    apt-get update 
    apt-get install -y  --no-install-recommends git  
    rm -rf /var/lib/apt/lists/*
EOF

RUN <<EOF
   useradd -s /bin/bash -m vscode
   groupadd docker
   usermod -aG  docker vscode
EOF

COPY . .

CMD ["hello","welcome to docker"]


