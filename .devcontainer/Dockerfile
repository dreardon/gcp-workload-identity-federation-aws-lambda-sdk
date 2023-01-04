FROM python:3.9.7

ENV PATH="/usr/local/bin/google-cloud-sdk/bin:${PATH}"

RUN apt-get update && \
    apt-get install -y zsh \
    curl \
    wget \
    git && \
    zsh --version && \
    usermod -s /usr/bin/zsh $(whoami) && \
    sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" && \
    curl -sSL https://sdk.cloud.google.com > /tmp/gcl && bash /tmp/gcl --install-dir=/usr/local/bin --disable-prompts && \
    gcloud components install beta
