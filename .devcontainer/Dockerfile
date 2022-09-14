FROM plantuml/plantuml-server:latest 

USER root 
RUN apt-get update ; \
    apt-get install -y \
        python3 \
        pip \
        unzip \
        git \
        sudo \ 
        ssh

ADD requirements.txt /
RUN pip install -r /requirements.txt

RUN unzip /var/lib/jetty/webapps/ROOT.war -d /plantuml/ ; \
    find /plantuml/ -name 'plantuml*.jar' -exec mv {} /plantuml/plantuml.jar \;

RUN chmod 777 /tmp/jetty/

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME -s /bin/bash \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME


CMD bash  
