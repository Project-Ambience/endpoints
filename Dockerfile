FROM vault.habana.ai/gaudi-docker/1.21.1/rhel9.4/habanalabs/pytorch-installer-2.6.0:latest

WORKDIR /app

RUN dnf install -y git-lfs && \
    dnf clean all

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN git clone https://github.com/hiyouga/LLaMA-Factory.git /app/LLaMA-Factory

COPY download_model.py .

EXPOSE 8000

CMD ["/bin/bash"]


