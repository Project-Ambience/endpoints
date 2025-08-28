# 🚀 LLMedic 

Customising Large Language Models for clinical workflows could improve healthcare delivery, but their
integration is constrained by regulatory requirements and clinicians’ limited technical expertise. Existing
fine-tuning frameworks are dependent on technical setup and lack clinician-centred interfaces, limiting
the practical application of LLMs in healthcare. To address these challenges, we developed LLMedic, an
on-premise platform leveraging Intel Gaudi 2 hardware that allows clinicians to discover open-source models,
fine-tune them locally, apply prompt-engineering strategies (Chain-of-Thought, Few-shot), and compare
different model outputs. LLMedic uses a modular microservices architecture for modular development and
robust handling of long-running operations. 

---

## Architecture Diagram

<img width="504" height="239" alt="image" src="https://github.com/user-attachments/assets/d0574263-e168-4abb-9905-dfa557468f5b" />

---

## Deployment

1. Clone both repos

```
git clone git@github.com:Project-Ambience/web-demo.git
```

```
git clone git@github.com:Project-Ambience/endpoints.git
```

2. Create .env (copy and paste .env into your file)

```
cd web-demo
nano .env
```

3. Run deploy script

cd back to root

```
cd endpoints
chmod +x ./admin/deploy_llmedic.sh
./admin/deploy_llmedic.sh dev
```

## Run in local (with docker)

```
docker-compose -f docker-compose.rabbitmq.yml up --build
docker-compose -f docker-compose.dev.yml up --build
docker-compose -f docker-compose.dev.yml exec api bin/rails db:migrate
(optional) docker-compose -f docker-compose.dev.yml exec api bin/rails db:seed
```
The app will available at port 5090

---

## Environment Variables for web service

Create a `.env` file in your project root:

```
RAILS_MASTER_KEY=
MODEL_INSTALLER_SERVICE_PATH=http://128.16.12.219:8001/models/install
MODEL_INSTALL_REQUEST_CALLBACK_PATH=http://128.16.12.219:5091/api/model_install_requests/update_status
MODEL_FINE_TUNE_REQUEST_CALLBACK_PATH=http://128.16.12.219:5091/api/model_fine_tune_requests/update_status
MODEL_FINE_TUNE_REQUEST_QUEUE_NAME=model_fine_tune_requests
MODEL_FORMATTING_REQUEST_QUEUE_NAME=model_formatting_requests
USER_PROMPT_QUEUE_NAME=user_prompts
DOMAIN=128.16.12.219
PORT=5091
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_PORT=5672
REDIS_URL=redis://redis:6379/1
RAG_DATA_ADDING_PATH=http://128.16.12.219:8000/documents/upload
RAG_DATA_ADDING_API_KEY=
```

`Note:` in local change 128.16.12.219 into your host IP and also make change in REACT_APP_CABLE_URL (in docker-compose.dev.yml)
