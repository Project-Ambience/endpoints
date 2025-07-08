#!/usr/bin/env python3
import pika, json, os

RABBIT_URL = os.environ.get("RABBIT_URL", "amqp://guest:guest@localhost:5672/")
QUEUE    = os.environ.get("QUEUE_NAME", "fine_tune_requests")

msg = {
  "fine_tune_request_id": 42,
  "ai_model_path":        "m42-health/Llama3-Med42-8B",               
  "parameters":           "{}",
  "fine_tune_data": [{
    "text": "### Instruction:\nSummarize the following doctor-patient dialogue into a clinical note.\n### Input:\nDoctor: Hi there, sir! How are you today? \r\nPatient: Hello! I am good.\r\nDoctor: I would like to start with your family medical history today. What do you know about their medical history? \r\nPatient: My mother and father both had heart disease. Well, my mother had complication from her heart disease and that is how she passed.  My father was only in his forty's when he died. \r\nDoctor: I am so sorry the hear that. \r\nPatient: Thank you. I have two brothers, one whom I don't speak to very much anymore. I don't know if he has any health problems. My other brother is healthy with no issues. Both my uncles on my mother's side had polio, I think. \r\nDoctor: Tell me more about your uncles with polio. They both had polio? \r\nPatient: One of them had to wear crutches due to how bad his leg deformans were and then the other had leg deformities in only one leg.  I am fairly certain that they had polio.  \r\nDoctor: Do you know of any other family member with neurological conditions?\r\nPatient: No. None that I know of. \r\nDoctor: Do you have any children? \r\nPatient: Yes. I have one child. \r\nDoctor: Is your child healthy and well? \r\nPatient: Yes.\n### Response:\nHis mother died of complications from heart disease.  His father died of heart disease in his 40s.  He has two living brothers.  One of them he does not speak too much with and does not know about his medical history.  The other is apparently healthy.  He has one healthy child.  His maternal uncles apparently had polio.  When I asked him to tell me further details about this, he states that one of them had to wear crutches due to severe leg deformans and then the other had leg deformities in only one leg.  He is fairly certain that they had polio.  He is unaware of any other family members with neurological conditions."
  },
  {
    "text": "### Instruction:\nSummarize the following doctor-patient dialogue into a clinical note.\n### Input:\nDoctor: Can you tell me about any diseases that run in your family? \r\nPatient: Sure, my brother has a prostate cancer.\r\nDoctor: Okay, brother.\r\nPatient: My father had brain cancer.\r\nDoctor: Okay, dad.\r\nPatient: Then on both sides of my family there are many heart related issues.\r\nDoctor: Okay.\r\nPatient: And my brother and sister both have diabetes.\r\nDoctor: Okay.\r\nPatient: Yes, that's it.\n### Response:\nHis brothers had prostate cancer.  Father had brain cancer.  Heart disease in both sides of the family.  Has diabetes in his brother and sister."
  },
  {
    "text": "### Instruction:\nSummarize the following doctor-patient dialogue into a clinical note.\n### Input:\nDoctor: Have you had any anxiety attacks lately? \r\nPatient: No.\r\nDoctor: Have you felt depressed or had any mood swing problems? \r\nPatient: No.\r\nDoctor: Any phobias?\r\nPatient: No, not really. \r\nDoctor: Okay.\n### Response:\nPSYCHIATRIC: Normal; Negative for anxiety, depression, or phobias."
  },
  {
    "text": "### Instruction:\nSummarize the following doctor-patient dialogue into a clinical note.\n### Input:\nDoctor: Do you have a history of mental illness or psychological disease? \r\nPatient: No.\n### Response:\nNone Past Psychological History: None"
  },
  {
    "text": "### Instruction:\nSummarize the following doctor-patient dialogue into a clinical note.\n### Input:\nDoctor: Hello sir. How are you doing today? You still look a little uncomfortable. Is there still pain?\r\nPatient: Yeah. Still a good amount of pain. I did not take my pain medication this morning though. Not sure if that will make a huge difference. \r\nDoctor: That is possibly why you are still in pain. How is movement? Can you get out of the house and get around?\r\nPatient: Yes. I am quite happy that I can do my daily activities. I can get up with minimal assistance and do many activities out of the house. I think I am gaining muscle from moving around more too. \r\nDoctor: How is the home exercise program going?\r\nPatient: I am loving pool therapy. I really feel like that is helping. I do the home exercises sometimes twice a day. I really want to get back to normal.\n### Response:\nThe patient states pain still significant, primarily 1st seen in the morning.  The patient was evaluated 1st thing in the morning and did not take his pain medications, so objective findings may reflect that.  The patient states overall functionally he is improving where he is able to get out in the house and visit and do activities outside the house more.  The patient does feel like he is putting on more muscle girth as well.  The patient states he is doing well with his current home exercise program and feels like pool therapy is also helping as well."
  }
],
  "callback_url":         "http://localhost:8000/callback",
  "signature":            "dummy-signature"
}

conn = pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
chan = conn.channel()
chan.queue_declare(queue=QUEUE, durable=True)
chan.basic_publish(
    exchange="",
    routing_key=QUEUE,
    body=json.dumps(msg),
    properties=pika.BasicProperties(delivery_mode=2)
)
print("→ Sent test message to queue")
conn.close()
