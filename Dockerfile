FROM vault.habana.ai/gaudi-docker/1.21.1/rhel9.4/habanalabs/pytorch-installer-2.6.0:latest

WORKDIR /app

RUN dnf install -y git-lfs && \
    dnf clean all

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN git clone https://github.com/huggingface/optimum-habana.git /app/optimum-habana && \
    cd /app/optimum-habana && \
    python3 setup.py install && \
    cd examples/language-modeling && \
    pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir git+https://github.com/HabanaAI/DeepSpeed.git


COPY download_model.py .
COPY inference ./inference
COPY start_download.sh .
COPY start_inference.sh .
COPY start_finetune.sh .

RUN chmod +x start_download.sh start_inference.sh start_finetune.sh

EXPOSE 8001


