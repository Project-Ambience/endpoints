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
COPY inference .
COPY start.sh .

EXPOSE 8001

RUN chmod +x start.sh

CMD ["bash", "start.sh"]


