FROM continuumio/anaconda3 as openvsp
RUN apt-get update
ENV TZ=Europe/Minsk
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get install -y wget cmake libxml2-dev g++ libjpeg-dev libglm-dev libeigen3-dev libcminpack-dev libglew-dev swig
WORKDIR /
RUN wget -O - https://github.com/OpenVSP/OpenVSP/tarball/OpenVSP_3.38.0 | tar xz
RUN mkdir -p /OpenVSP-OpenVSP-e5d6748/SuperProject/build
RUN mkdir -p /usr/local/openvsp
WORKDIR /OpenVSP-OpenVSP-e5d6748/SuperProject/build
RUN cmake .. \
        -DCMAKE_INSTALL_PREFIX=/usr/local/openvsp \
        -DVSP_NO_GRAPHICS=true \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_PREFIX_PATH='/usr' \
        -DVSP_USE_SYSTEM_CPPTEST=false \
        -DVSP_USE_SYSTEM_LIBXML2=true \
        -DVSP_USE_SYSTEM_EIGEN=true \
        -DVSP_USE_SYSTEM_CODEELI=false \
        -DVSP_USE_SYSTEM_FLTK=false \
        -DVSP_USE_SYSTEM_GLM=true \
        -DVSP_USE_SYSTEM_GLEW=true \
        -DVSP_USE_SYSTEM_CMINPACK=true \
        -DPYTHON_EXECUTABLE='/opt/conda/bin/python' \
        -DPYTHON_LIBRARY='/opt/conda/lib' \
        -DPYTHON_INCLUDE_DIR='/opt/conda/include/python3.8' \
        -DPYTHON_INCLUDE_PATH='/opt/conda/include'
RUN make

RUN mkdir -p /usr/local/openvsp 
RUN cp /OpenVSP-OpenVSP-e5d6748/SuperProject/build/OpenVSP-prefix/src/OpenVSP-build/OpenVSP-3.38.0-Linux.zip /usr/local/openvsp

RUN mkdir -p /opt/conda/lib/python3.8/site-packages/openvsp

RUN apt install unzip -y

WORKDIR /usr/local/openvsp
RUN unzip OpenVSP-3.38.0-Linux.zip
WORKDIR /usr/local/openvsp/OpenVSP-3.38.0-Linux/python/utilities
RUN pip install .
WORKDIR /usr/local/openvsp/OpenVSP-3.38.0-Linux/python/degen_geom
RUN pip install .
WORKDIR /usr/local/openvsp/OpenVSP-3.38.0-Linux/python/openvsp_config
RUN pip install .
WORKDIR /usr/local/openvsp/OpenVSP-3.38.0-Linux/python/openvsp
RUN pip install .
WORKDIR /usr/local/openvsp/OpenVSP-3.38.0-Linux/python/AvlPy
RUN pip install .

WORKDIR /vsptools
COPY requirements.txt .
RUN pip install -r requirements.txt

ENV PATH="/usr/local/openvsp:${PATH}"

CMD ["/bin/bash"]
