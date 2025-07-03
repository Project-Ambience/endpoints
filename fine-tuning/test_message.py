#!/usr/bin/env python3
import pika, json, os

RABBIT_URL = os.environ.get("RABBIT_URL", "amqp://guest:guest@localhost:5672/")
QUEUE    = os.environ.get("QUEUE_NAME", "fine_tune_requests")

msg = {
  "fine_tune_request_id": 42,
  "ai_model_path":        "m42-health/Llama3-Med42-8B",               
  "parameters":           "{\"learning_rate\":0.01}",
  "fine_tune_data": [
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: What brings you back into the clinic today, miss? \r\nPatient: I came in for a refill of my blood pressure medicine. \r\nDoctor: It looks like Doctor Kumar followed up with you last time regarding your hypertension, osteoarthritis, osteoporosis, hypothyroidism, allergic rhinitis and kidney stones.  Have you noticed any changes or do you have any concerns regarding these issues?  \r\nPatient: No. \r\nDoctor: Have you had any fever or chills, cough, congestion, nausea, vomiting, chest pain, chest pressure?\r\nPatient: No.  \r\nDoctor: Great. Also, for our records, how old are you and what race do you identify yourself as?\r\nPatient: I am seventy six years old and identify as a white female.",
      "output": "The patient is a 76-year-old white female who presents to the clinic today originally for hypertension and a med check.  She has a history of hypertension, osteoarthritis, osteoporosis, hypothyroidism, allergic rhinitis and kidney stones.  Since her last visit she has been followed by Dr. Kumar.  Those issues are stable.  She has had no fever or chills, cough, congestion, nausea, vomiting, chest pain, chest pressure."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How're you feeling today?  \r\nPatient: Terrible. I'm having the worst headache of my life. \r\nDoctor: I'm so sorry. Well you are only twenty five, so let's hope this is the last of the worst. Let's see how we can best help you. When did it start? \r\nPatient: Around eleven in the morning. \r\nDoctor: Today? \r\nPatient: Um no yesterday. July thirty first. \r\nDoctor: July thirty first O eight. Got it. Did it come on suddenly? \r\nPatient: Yeah. \r\nDoctor: Are you having any symptoms with it, such as blurry vision, light sensitivity, dizziness, lightheadedness, or nausea? \r\nPatient: I'm having blurry vision and lightheadedness.  I also can't seem to write well. It looks so messy. I am naturally right handed but my writing looks like I am trying with my left. \r\nDoctor: How would you describe the lightheadedness? \r\nPatient: Like there are blind spots. \r\nDoctor: Okay. How about any vomiting? \r\nPatient: Um no. I feel like my face is pretty swollen though. I don't know if it's related to the headache but it started around the same time. \r\nDoctor: Here in the E R, we'll do a thorough exam and eval to make sure nothing serious is going on. While we're waiting for your C T results, I'm going to order a migraine cocktail and some Morphine. \r\nPatient: Thank. Will the nurse be in soon? \r\nDoctor: Yes, she'll be right in as soon as the order is placed. It shouldn't be more than a few minutes. If it takes longer, then please ring the call bell.",
      "output": "The patient is a 25-year-old right-handed Caucasian female who presented to the emergency department with sudden onset of headache occurring at approximately 11 a.m. on the morning of the July 31, 2008.  She described the headache as worse in her life and it was also accompanied by blurry vision and scotoma.  The patient also perceived some swelling in her face.  Once in the Emergency Department, the patient underwent a very thorough evaluation and examination.  She was given the migraine cocktail.  Also was given morphine a total of 8 mg while in the Emergency Department.  For full details on the history of present illness, please see the previous history and physical."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello, miss. What is the reason for your visit today? \r\nPatient: I think I have some warts on my back end where the poop comes out. \r\nDoctor: I see. When did you start noticing them? \r\nPatient: I think like three to four weeks ago. \r\nDoctor: Do you feel any pain or discomfort? \r\nPatient: It itches a little, but I haven't felt any pain yet. Is this normal for a twenty two year old? \r\nDoctor: I'll have to take a look, but you'll be fine. Are there any other symptoms that you are aware of?\r\nPatient: Nope. Just the warts and itchiness.",
      "output": "This is a 22-year-old female, who presented to the office complaining of condylomas she had noted in her anal region.  She has noticed approximately three to four weeks ago.  She denies any pain but does state that there is some itching.  No other symptoms associated."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Are you taking any over the counter medicines? \r\nPatient: No, only the ones which were prescribed.\r\nDoctor: No alternative medicine, naturopathy or anything?\r\nPatient: No, only whatever is here in this prescription. \r\nDoctor: Okay let me take a look...so you were prescribed Salmeterol inhaler-\r\nPatient: On as needed basis.\r\nDoctor: Okay and the other one is Fluticasone inhaler, which is-\r\nPatient: Which is a nasal inhaler.\r\nDoctor: Right.",
      "output": "Prescribed medications were Salmeterol inhaler, prn; and Fluticasone nasal inhaler. The patient was taking no over the counter or alternative medicines."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hi, how are you? \r\nPatient: I burned my hand.\r\nDoctor: Oh, I am sorry. Wow!\r\nPatient: Yeah.\r\nDoctor: Is it only right arm?\r\nPatient: Yes.",
      "output": "Burn, right arm."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How's your asthma since you started using your inhaler again? \r\nPatient: Much better. I don't know why I didn't take it with me everywhere I went. \r\nDoctor: It's important to carry it with you, especially during times where you're exercising or walking more than usual. \r\nPatient: Yeah. I think I've learned my lesson. \r\nDoctor: Besides asthma, do you have any other medical problems?",
      "output": "Asthma."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you smoke? \r\nPatient: No, I quit before I had my daughter. \r\nDoctor: Are you currently pregnant?\r\nPatient: No, I'm not. \r\nDoctor: Did you have any complications with the birth of your daughter? \r\nPatient: I actually had a C section. \r\nDoctor: Have you had any other surgeries in the past? \r\nPatient: I got my appendix out a few years ago. \r\nDoctor: Do you have any other issues, like high blood pressure or heart disease?\r\nPatient: No. \r\nDoctor: Do you have diabetes? \r\nPatient: No. \r\nDoctor: Are there any problems with the lungs, thyroid, kidney, or bladder? \r\nPatient: No. \r\nDoctor: So, how long ago did you hurt your lower back? \r\nPatient: It was about four or five years ago now, when I was in a car crash. \r\nDoctor: What kind of treatments were recommended? \r\nPatient: They didn't recommend P T, and I didn't really have any increased back pain after the accident.",
      "output": "The patient denies high blood pressure, diabetes, heart disease, lung disease, thyroid, kidney, or bladder dysfunctions.  The patient stated that she quit smoking prior to her past childbirth and is currently not pregnant.  The patient has had a C-section and also an appendectomy.  The patient was involved in a motor vehicle accident four to five years ago and at that time, the patient did not require any physical therapy nor did she report any complaints of increased back pain following that accident."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Any know drug allergies? \r\nPatient: No.",
      "output": "No known drug allergies."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hi there, sir! How are you today? \r\nPatient: Hello! I am good.\r\nDoctor: I would like to start with your family medical history today. What do you know about their medical history? \r\nPatient: My mother and father both had heart disease. Well, my mother had complication from her heart disease and that is how she passed.  My father was only in his forty's when he died. \r\nDoctor: I am so sorry the hear that. \r\nPatient: Thank you. I have two brothers, one whom I don't speak to very much anymore. I don't know if he has any health problems. My other brother is healthy with no issues. Both my uncles on my mother's side had polio, I think. \r\nDoctor: Tell me more about your uncles with polio. They both had polio? \r\nPatient: One of them had to wear crutches due to how bad his leg deformans were and then the other had leg deformities in only one leg.  I am fairly certain that they had polio.  \r\nDoctor: Do you know of any other family member with neurological conditions?\r\nPatient: No. None that I know of. \r\nDoctor: Do you have any children? \r\nPatient: Yes. I have one child. \r\nDoctor: Is your child healthy and well? \r\nPatient: Yes.",
      "output": "His mother died of complications from heart disease.  His father died of heart disease in his 40s.  He has two living brothers.  One of them he does not speak too much with and does not know about his medical history.  The other is apparently healthy.  He has one healthy child.  His maternal uncles apparently had polio.  When I asked him to tell me further details about this, he states that one of them had to wear crutches due to severe leg deformans and then the other had leg deformities in only one leg.  He is fairly certain that they had polio.  He is unaware of any other family members with neurological conditions."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Can you tell me about any diseases that run in your family? \r\nPatient: Sure, my brother has a prostate cancer.\r\nDoctor: Okay, brother.\r\nPatient: My father had brain cancer.\r\nDoctor: Okay, dad.\r\nPatient: Then on both sides of my family there are many heart related issues.\r\nDoctor: Okay.\r\nPatient: And my brother and sister both have diabetes.\r\nDoctor: Okay.\r\nPatient: Yes, that's it.",
      "output": "His brothers had prostate cancer.  Father had brain cancer.  Heart disease in both sides of the family.  Has diabetes in his brother and sister."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Good afternoon, ma'am. Welcome to A B C D General Hospital. Before we begin, I just need to confirm some background information on you. \r\nPatient: Good afternoon, doctor. Absolutely, that's no problem. \r\nDoctor: First, how old are you?\r\nPatient: I'm nineteen, sir. \r\nDoctor: Good, and your chart says you identify as Caucasian. Is that correct? \r\nPatient: Yes, sir, that's correct. \r\nDoctor: Great, what seems to be problem today, ma'am?\r\nPatient: I've had this bunion on my foot for such a long time. \r\nDoctor: How long has this bunion been present? \r\nPatient: At this point, um, I don't even remember how long it's been. \r\nDoctor: Do you have any other conditions that I should be aware of?\r\nPatient: Actually, yes. I have a history of, um, Charcot Marie tooth disease. \r\nDoctor: That's good to know, thank you. \r\nPatient: I would like to have surgery to cut this bunion off, I can't take it anymore.",
      "output": "This 19-year-old Caucasian female presents to ABCD General Hospital.  The patient states she has had worsening bunion deformity for as long as she could not remember.  She does have a history of Charcot-Marie tooth disease and desires surgical treatment at this time."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: I hear someone has a birthday coming up, how old are you turning, ma'am?\r\nPatient: I'll be ninety later this month, doctor. \r\nDoctor: You're here for a follow up not very long after your first visit. What seems to be the problem today? \r\nPatient: Well, actually, my high blood pressure and right arm symptoms are basically gone. \r\nDoctor: Great, I saw your blood pressure reading for today, and it's much better. Are you taking the higher dose of Mavik we recommended? \r\nPatient: No, I'm not taking that right now. \r\nDoctor: How did you tolerate the higher dose? \r\nPatient: I didn't feel well at all, so I just went back to the old dose. \r\nDoctor: That was one M G per day, correct? \r\nPatient: Yes, doctor. I do think I could have some white coat high blood pressure. Doctors' offices make me nervous. \r\nDoctor: That does happen. Here, try this sample of Tarka, please. \r\nPatient: What is this for, doctor? \r\nDoctor: Well, since you're taking the Mavik plus verapamil, you can switch over to Tarka, which is the combined version of the two drugs. \r\nPatient: I can't take these, doctor. They're too big. \r\nGuest_family: Hello doctor, I'm her daughter. Just so you know, we check her blood pressure at home periodically and it's always similar to that reading. \r\nDoctor: Good, so back to that right arm, how is that doing today?\r\nPatient: Well, that pain is basically gone now, I think it had to do with that muscle problem back in my right shoulder blade. \r\nDoctor: Did you have x rays taken today? \r\nPatient: Yes, the tech brought me back right before you came in. \r\nDoctor: Good, I have the images right here. \r\nPatient: What do they show, doctor?\r\nDoctor: Well, these x rays of the neck and right shoulder show some degenerative changes, and possibly some kind of rotator cuff injury. \r\nPatient: What makes you think there's an injury? \r\nDoctor: Well, look right here. The humeral head is pretty high in the glenoid in the right shoulder, but do you have any pain here? \r\nPatient: No, none. \r\nDoctor: Then we won't worry about it. \r\nPatient: I am having this stomach pain though, doctor.\r\nDoctor: How has this pain developed and progressed recently? \r\nPatient: Well, it's improved somewhat with me not taking Aleve anymore. \r\nDoctor: What medicines are you taking right now, then? \r\nPatient: Right know, I'm just taking Tylenol as needed. That seems to be enough for me. \r\nDoctor: Do you think this could be acid reflux, or heartburn?\r\nPatient: No, but I take Tums, um, three times a day, and Mylanta at night. Oh yeah, I have these sores in my mouth, can you take a look? \r\nDoctor: I see. How long have you worn dentures? \r\nPatient: Oh I couldn't even tell you, it's been many, many years. \r\nDoctor: Do they come and go, the sores? \r\nPatient: Yes, one will come, then it'll heal up, then another. \r\nDoctor: Okay, we'll keep an eye on it. \r\nPatient: And doctor, since I've been taking the Lexapro, I have some tremors on basically my whole body, at least the upper body, like my torso and arms. \r\nDoctor: It's hard to tell if you have a tremor today, ma'am, but do you think the Lexapro is helping otherwise? \r\nPatient: Yes, we think so.",
      "output": "The patient is an 89-year-old lady.  She actually turns 90 later this month, seen today for a short-term followup.  Actually, the main reasons we are seeing her back so soon which are elevated blood pressure and her right arm symptoms are basically resolved.  Blood pressure is better even though she is not currently on the higher dose Mavik likely recommended.  She apparently did not feel well with the higher dose, so she just went back to her previous dose of 1 mg daily.  She thinks, she also has an element of office hypertension.  Also, since she is on Mavik plus verapamil, she could switch over to the combined drug Tarka.  However, when we gave her samples of that she thought they were too big for her to swallow.  Basically, she is just back on her previous blood pressure regimen.  However, her blood pressure seems to be better today.  Her daughter says that they do check it periodically and it is similar to today's reading.  Her right arm symptoms are basically resolved and she attributed that to her muscle problem back in the right shoulder blade.  We did do a C-spine and right shoulder x-ray and those just mainly showed some degenerative changes and possibly some rotator cuff injury with the humeral head quite high up in the glenoid in the right shoulder, but this does not seem to cause her any problems.  She has some vague 'stomach problems', although apparently it is improved when she stopped Aleve and she does not have any more aches or pains off Aleve.  She takes Tylenol p.r.n., which seems to be enough for her.  She does not think she has any acid reflux symptoms or heartburn.  She does take Tums t.i.d. and also Mylanta at night.  She has had dentures for many, many years and just recently I guess in the last few months, although she was somewhat vague on this, she has had some sores in her mouth.  They do heal up, but then she will get another one.  She also thinks since she has been on the Lexapro, she has somewhat of a tremor of her basically whole body at least upper body including the torso and arms and had all of the daughters who I not noticed to speak of and it is certainly difficult to tell her today that she has much tremor.  They do think the Lexapro has helped to some extent."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor:  Are you talking any medications?\r\nPatient: No, I don't believe in meds.\r\nDoctor: Oh really, let me check your list.\r\nPatient: Yeah never.\r\nDoctor: Wow amazing.",
      "output": "None."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Any past medical history? \r\nGuest_family: She has a history of peptic ulcer disease and we think she may have had a possible stroke three or four years ago. I would have to double check. \r\nDoctor: Let me see if I can find it in her records.  \r\nDoctor: Does she see a neurologist? \r\nGuest_family: Um I'm not sure. I can call her son? \r\nDoctor: Yes, if you could find out that'd be great.  \r\nGuest_family: She's also experiencing some memory loss as of one to two years ago. I think that's it for medical history.",
      "output": "PUD, ?stroke and memory difficulty in the past 1-2 years."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How old are you? \r\nPatient: I am forty four. \r\nDoctor: Are you right handed or left handed? \r\nPatient: I'm right handed. \r\nDoctor: Tell me what happened. \r\nPatient: I don't know. I woke up over this numbness on my left side of the body. I remember it was on July twenty nineth. \r\nDoctor: Was there any sensation like having pins and needles? Was there any weakness? Is there any change in your visual or mental status? Were you able to walk? \r\nPatient: I was able to walk and there was no weakness or any other thing you mentioned. \r\nDoctor: When did you first start noticing these symptoms? \r\nPatient: There was nothing around Independence Day. It all started after that. At first, I felt that my right hand is very clumsy, and it is kind of stiff. Then I noticed leaning towards the right when walking. It was strange. Happened around July seventh.\r\nDoctor: Did you recently have any cold or flu like symptoms? \r\nPatient: No. \r\nDoctor:  Were diagnosed with a thing called multiple sclerosis? \r\nPatient: No. \r\nDoctor: Did you ever have a feeling where you felt like there's an electric is going up or down your spine? \r\nPatient: No. \r\nDoctor: How about any fatigue or pain? Any frequency in your urination? Any urgency in that? \r\nPatient: No.",
      "output": "This 44y/o RHF awoke on 7/29/93 with left hemibody numbness without tingling, weakness, ataxia, visual or mental status change. She had no progression of her symptoms until 7/7/93 when she notices her right hand was stiff and clumsy. She coincidentally began listing to the right when walking. She denied any recent colds/flu-like illness or history of multiple sclerosis. She denied symptoms of Lhermitte's or Uhthoff's phenomena."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: You had a heart surgery, right?\r\nPatient: Yes, that is right.\r\nDoctor: Pacemaker?\r\nPatient: Yes, they did that.\r\nDoctor: What else? What other surgeries?\r\nPatient: I have had a hysterectomy.\r\nDoctor: Okay.\r\nPatient: Yeah.",
      "output": "Placement of pacemaker and hysterectomy."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How old are you, young boy?\r\nPatient: I am twenty nine. \r\nDoctor: And you got right side shoulder pain? Is this something new?\r\nPatient: Yes. That is right.\r\nDoctor: What were you doing when this happened?\r\nPatient: I think I was picking up a stack of cardboard, then putting it down on the ground and twisting to the right side. And sometimes I was throwing them a little bit as well.\r\nDoctor: Okay, and how far you were lifting them or bending?\r\nPatient: Around here, till waist level.\r\nDoctor: Okay.\r\nPatient: I heard a pop and since then there is pain in this area. I can't lift heavy items. Basically I have no strength.\r\nDoctor: Okay. And this all started from June thirty two thousand and four?\r\nPatient: Yes, that's right. The pain is in the lateral part of the back of my shoulder. \r\nDoctor: How did you lose your arm if I may ask?\r\nPatient: Motorcycle accident.",
      "output": "This is the initial clinic visit for a 29-year-old man who is seen for new onset of right shoulder pain.  He states that this began approximately one week ago when he was lifting stacks of cardboard.  The motion that he describes is essentially picking up a stack of cardboard at his waist level, twisting to the right and delivering it at approximately waist level.  Sometimes he has to throw the stacks a little bit as well.  He states he felt a popping sensation on 06/30/04.  Since that time, he has had persistent shoulder pain with lifting activities.  He localizes the pain to the posterior and to a lesser extent the lateral aspect of the shoulder.  He has no upper extremity ."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: When did the nausea and vomiting start? \r\nPatient: About a few hours ago. I can't seem to stomach anything. \r\nDoctor: How many episodes of vomiting have you had? \r\nPatient: At least four. \r\nDoctor: Any abdominal pain, fever, chill, or other symptoms? \r\nPatient: Just nausea and vomiting. It's been so terrible. \r\nDoctor: I'll order you some Zofran to help bring the nausea to bay. One moment while I put the order in.",
      "output": "Intractable nausea and vomiting."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Good afternoon, ma'am. \r\nPatient: Good afternoon, doctor. \r\nDoctor: Is this your assistant, ma'am? \r\nPatient: Yes, she helps me out all day.  \r\nDoctor: Great, do you have your food diary sheets? \r\nPatient: Yes, can you give them to her, please? \r\nDoctor: Thank you. What are you doing for exercise? \r\nPatient: Um, right now, I walk around at the mall to get my steps in every day.",
      "output": "The patient's assistant brings in her food diary sheets.  The patient says she stays active by walking at the mall."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Is he currently taking any medication? \r\nGuest_family: No.",
      "output": "None."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello, sir. I see your last visit was on July two thousand and seven. What was the reason for that visit?  \r\nPatient: My asthma was acting up, and it felt like I couldn't breathe. \r\nDoctor: Do you have a history of asthma? \r\nPatient: Not that I know of, but I know I always get this really bad cough where I cough up some nasty phlegm. \r\nDoctor: I see. I'm looking at your report and it says you have a history of pneumonia.",
      "output": "Asthma with his last admission in 07/2007.  Also inclusive of frequent pneumonia by report."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you know about any medical traits in your family? \r\nPatient: No, everyone in my family is quite healthy. I'm not aware of any medical problems. \r\nDoctor: Are you sexually active? \r\nPatient: Yes, I am with my boyfriend. \r\nDoctor: Do you take any drugs or alcohol or smoke? \r\nPatient: No, none of them.",
      "output": "completely unremarkable FHx. Has boyfriend and is sexually active. Denied drug/ETOH/Tobacco use."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Any past medical history? \r\nPatient: Um there were a couple times where I noticed my blood pressure was high but that's improved as of late. \r\nDoctor: When did these episodes occur? \r\nPatient: About a year ago. \r\nDoctor: Did you follow up with your previous doctor? \r\nPatient: Yeah, my old doctor knows. \r\nDoctor: Okay then. Let's see. Have you been checking your own blood pressure as a result? \r\nPatient: No not really.  \r\nDoctor: It looks like your blood pressure was normal today, which is a good sign. \r\nPatient: Great. \r\nDoctor: Hm any allergies to medications? \r\nPatient: None that I know of. \r\nDoctor: And it looks like you have gained about fourteen pounds since last year. Any new diet changes or stressors? \r\nPatient: I lost my job last January and it took a pretty big toll on me. \r\nDoctor: I'm sorry to hear that. How have you been coping? \r\nPatient: I'm doing better now but I need to watch what I eat. I tend to eat a lot more when I'm stressed. It's something I'm working on.",
      "output": "Unremarkable.  There is no history of allergies.  He does have some history of some episodes of high blood pressure, and his weight is up about 14 pounds from the last year."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Are you allergic to anything?\r\nPatient: Yes, I am allergic to Penicillin.\r\nDoctor: Any other drugs that you could be allergic to?\r\nPatient: Nope that is all.\r\nDoctor: Okay.",
      "output": "Penicillin."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Guest_clinician: What brought them in today? \r\nDoctor: Poor renal sufficiency, possibly due to dehydration or diabetic nephropathy. She also has high blood pressure and low blood sugar as a result of missing meals regularly.",
      "output": "1.  Hypoglycemia due to not eating her meals on a regular basis. 2.  Hypertension. 3.  Renal insufficiency, may be dehydration, or diabetic nephropathy."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Patient: Doc what are you going to diagnose me as?\r\nDoctor: We are looking at blood born pathogen exposure secondary to needlestick. \r\nPatient: Yes, I was also thinking around contamination.",
      "output": "Blood-borne pathogen exposure secondary to contaminated needlestick."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Guest_clinician: She was in a car crash, correct? \r\nDoctor: Correct. About two days ago. I believe it was a head on collision.",
      "output": "Motor vehicle accident."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Any allergies I should know about? \r\nPatient: Nope, no allergies for me.",
      "output": "No allergies."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello sir. Let me first start by asking your age. How old are you? \r\nPatient: I'm twenty four.  \r\nDoctor: So, what brought you here? How can I help you? \r\nPatient: I was out for fishing this weekend, I think I got into some poison ivy and I have these rashes all over my chest, legs, arms and also some are on my back. \r\nDoctor: You seem so confident of it being poison ivy has it happened before? \r\nPatient: Oh yes, it has happened several times before. It usually takes some time to get over. Last time I was here Doctor Blackman gave me a steroid injection. \r\nDoctor: Okay, let me check my records. It looks like he gave you eighty milligrams of depomedrol. How was it last time after the injection? \r\nPatient: It worked fine. It did take us some time to get rid of it. \r\nDoctor: Did you take any medicine or anything else this time?\r\nPatient: I took over the counter Benadryl. Also, I'm applying cortisone cream on the rashes. \r\nDoctor: Did they help you? \r\nPatient: I saw a little bit of improvement. But this weekend it seemed to have been worst.\r\nDoctor: No worries, let's set you up for another injection.",
      "output": "He is a 24-year-old male who said that he had gotten into some poison ivy this weekend while he was fishing.  He has had several cases of this in the past and he says that is usually takes quite awhile for him to get over it; he said that the last time he was here he got a steroid injection by Dr. Blackman; it looked like it was Depo-Medrol 80 mg.  He said that it worked fairly well, although it seemed to still take awhile to get rid of it.  He has been using over-the-counter Benadryl as well as cortisone cream on the areas of the rash and having a little bit of improvement, but this last weekend he must have gotten into some more poison ivy because he has got another outbreak along his chest, legs, arms and back."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: You had mentioned that cancer runs in your family. What type of cancer? \r\nPatient: Skin cancer. \r\nDoctor: Any other health problems in the family? \r\nPatient: High blood pressure.",
      "output": "Cancer, hypertension."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hi, what brings you here today?\r\nPatient: I feel this lump on the upper side of my breast. \r\nDoctor: Both sides? \r\nPatient: No, only on the left side. \r\nDoctor: Do you feel it deep inside or on the outer side?\r\nPatient: Only on the outer side.",
      "output": "Suspicious calcifications upper outer quadrant, left breast."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: I understand that you are new to the clinic. Welcome. \r\nPatient: Yes, I am new here. I have lived in Arizona for the last four years. I am from Maine. That is where I grow up and most of my family still lives there.  \r\nDoctor: What line of work are you in? \r\nPatient: I am a homemaker. I used to clean house, a while back.  \r\nDoctor: Do you have children? \r\nPatient: I have two children but only one of them is still with us. My oldest son passed away from ulcerative colitis complications three years ago.  \r\nDoctor: I am so sorry to hear that!",
      "output": "The patient is originally from Maine.  She has lived in Arizona for 4 years.  She has had 2 children; however, only one is living.  She had one child died from complications of ulcerative colitis.  She has been predominantly a homemaker during her life, but has done some domestic cleaning work in the past."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: You okay there? \r\nPatient: Uh yeah, sorry. I'm just trying to adjust the stretcher. \r\nDoctor: Want some help? \r\nPatient: No, thank you. I think I got it. \r\nDoctor: So how're you doing? \r\nPatient: Fine, but I have this weird lump in my chest. \r\nDoctor: When did you first notice it? \r\nPatient: It's been there for a while. I'd say almost half a year. \r\nDoctor: Have you seen anyone for it? \r\nPatient: No, not until now. \r\nDoctor: Is it causing you pain? And has it changed in size at all?\r\nPatient: Not really. It's just noticeable when I run my fingers over it. \r\nDoctor: Have you spotted any swelling or redness to the area? Any drainage? \r\nPatient: No. \r\nDoctor: I see. Okay. Let me take a look and then I'll have you walk down the hall to get an Xray so we can see what's going on.",
      "output": "Lump in the chest wall."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello, so you are here for follow up today. \r\nPatient: Yes, very much. \r\nDoctor: I will ask you some regular questions, okay? \r\nPatient: Sure. \r\nDoctor: Any pain in urination? \r\nPatient: Nope. \r\nDoctor: Any fever or chills? \r\nPatient: Neither of them. \r\nDoctor: Have you noticed any blood while urinating? Any blood in your urine? \r\nPatient: Nope. I do leak, especially when I'm changing my positions like from sitting to standing so I do feel there is some involuntary urination. It's more like a urge. I'm loading data in like every one hour in the morning, especially when I take that Lasix. \r\nDoctor: Does it taper off in the afternoon or night? \r\nPatient: It tapers off in the afternoon. And by the night I don't do not feel anything. \r\nDoctor: Any leakage in the night? \r\nPatient: Nope. \r\nDoctor: Do you apply a lot of force to urinate? \r\nPatient: Nope. \r\nDoctor: How about this stream? Is it good or less? Are you emptying well? And what about the bowel movement? \r\nPatient: The stream is good. It does feel like all is out in one go. I do not have any kind of bowel issues. I'm using my vaginal cream. Sometimes I feel difficulty in doing so because I feel that there is still something coming out from the vagina and I'm afraid that there might be a prolapse. \r\nDoctor: Don't worry, I will look into it.",
      "output": "The patient presents today for followup.  No dysuria, gross hematuria, fever, chills.  She continues to have urinary incontinence, especially while changing from sitting to standing position, as well as urge incontinence.  She is voiding daytime every 1 hour in the morning especially after taking Lasix, which tapers off in the afternoon, nocturia time 0.  No incontinence.  No straining to urinate.  Good stream, emptying well.  No bowel issues, however, she also indicates that while using her vaginal cream, she has difficulty doing this as she feels protrusion in the vagina, and very concerned if she has a prolapse."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Have you lost weight?\r\nPatient: No, I haven't, you can ask my daughter.\r\nDoctor: How about anything like fever, nausea, vomiting, pain?\r\nPatient: No.\r\nDoctor: And as we discussed you have problem talking and comprehending. \r\nPatient: Yes.\r\nDoctor: And you get urine infections too?\r\nPatient: Yes. \r\nDoctor: And as discussed, your drainage is similar to past episodes when you had such infection? \r\nPatient: Yes.",
      "output": "As in HPI. Patient and daughter also deny weight loss, fevers, chills, sweats, nausea, vomiting, abdominal pain. She has had some difficulty expressing herself, but seems to comprehend speech as above. The patient has had a history of chronic urinary tract infections and her drainage is similar to past episodes when she has had such infection."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you use tobacco products? Cigarettes, chewing tobacco or vaping? \r\nPatient: I used to smoke a pack a day.  I quit that awful habit in nineteen eighty five. \r\nDoctor: Do you work? \r\nPatient: I am retired.\r\nDoctor: Wonderful. Is your husband retired with you?\r\nPatient: Yes. We both are. I cannot imagine working a full time job at seventy six years old.",
      "output": "She is married.  A 76-year-old who used to smoke a pack a day and quit in 1985.  She is retired."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hi there, how are you?\r\nPatient: I am okay.\r\nDoctor: So, I see you turned eighty-eight yesterday, happy birthday!\r\nPatient: Thank you! \r\nDoctor: And you are referred by Doctor X, he is your primary physician, right?\r\nPatient: Correct! I am also seeing Doctor Y for my leukemia. \r\nDoctor: Hm he mentioned that it's chronic lymphocytic leukemia.\r\nPatient: Yes.\r\nDoctor: Okay.\r\nDoctor: And you are also seeing Doctor Z for your heart related problems.\r\nPatient: That is correct.\r\nDoctor: So, tell me what is happening with you?\r\nPatient: For the past one week I am having this increased shortness of breath and having difficulty breathing from past few nights while sleeping.\r\nDoctor: Okay.\r\nPatient: And this morning I was having difficulty catching my breath. I am also having wheezing since morning.\r\nDoctor: Let me examine you, can you come forward and sit-up here? Any chest discomfort or acute chest pain or anything of that sort? Any pain of the left arm?\r\nPatient: No.\r\nDoctor: Any dizziness, feeling like fainting or light headedness or losing control?\r\nPatient: No.\r\nDoctor: Well, I don't think there is any sign of cardiovascular accident or heart attack, so that's that. You do have mild peripheral edema. We need to treat that.\r\nPatient: Okay.",
      "output": "The patient is an 88-year-old gentleman followed by Dr. X, his primary care physician, Dr. Y for the indication of CLL and Dr. Z for his cardiovascular issues.  He presents to the Care Center earlier today with approximately a one-week history of increased progressive shortness of breath, orthopnea over the course of the past few nights, mild increase in peripheral edema, and active wheezing with dyspnea presenting this morning. He reports no clear-cut chest discomfort or difficulty with angina.  He has had no dizziness, lightheadedness, no near or true syncope, nothing supportive of CVA, TIA, nor peripheral vascular claudication."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Ready to go home?\r\nPatient: I just can't wait.\r\nDoctor: Sure. I can understand.\r\nPatient: Bye Doctor.\r\nDoctor: Yes. See you soon.",
      "output": "The patient will be going home."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello, sir. How are you today? Can you confirm your age?\r\nPatient: Fifty eight. I feel like my balance is off, and I've been feeling tired and weak. \r\nDoctor: How long have you been experiencing this? \r\nPatient: It's been going on for six to eight weeks. \r\nDoctor: I see. Did you feel any other symptoms? \r\nPatient: I haven't, but this might not be related. I had pneumonia ten days before this all started. \r\nDoctor: Interesting. Did you take any medication for that? \r\nPatient: I did, but I don't know how to pronounce it. I wrote it down for you to read. Here it is. \r\nDoctor: Let me take a look. I see you took a full course of amoxicillin, right? \r\nPatient: Yeah, that's right. \r\nDoctor: How did you feel after you finished the antibiotics? \r\nPatient: Terrible. I felt like I couldn't control my body. My balance got even worse, and I felt even more tired and weak.\r\nDoctor: Oh, wow. Do you know why your balance and coordination worsened? \r\nPatient: I did fall recently, but I know for a fact my balance was off before my fall. \r\nDoctor: How high were you when you fell?\r\nPatient: I think I was three or five feet high when I fell. \r\nDoctor: Did you fall on your back?\r\nPatient: No, I fell on my feet. Just kidding, I fell on my back.  \r\nDoctor: Funny. Did anything hurt after your fall?\r\nPatient: Not really, but I've been having some back pain in my lower and mid back. \r\nDoctor: Did you always have that pain? \r\nPatient: No, I haven't. It comes and goes. \r\nDoctor: Have you done anything to treat it? \r\nPatient: I started to see a chiropractor like five days ago. He adjusts my neck and lower back. \r\nDoctor: I see. Did you start having problems with your balance after this? \r\nPatient: No. I was still having problems with that before I saw the chiropractor. \r\nDoctor: Okay. So, it wasn't the result of the adjustments. Is there anything else that may have caused it? \r\nPatient: I was taking this other medicine for ten days, but I don't remember what it was for. Here is the name of the medication. I wrote it on another paper. \r\nDoctor: It looks like you took Cipro. This is usually used to treat a U T I. Were you aware you had a U T I?\r\nPatient: Oh, yeah. I forgot about that. I thought I had one, so I went to another doctor to get some medication. \r\nDoctor: I see. I have one more question. Do you have any trouble controlling your bowel movements or attempting to go to the bathroom? \r\nPatient: Nope. I feel like I'm able to go to the bathroom whenever I want.",
      "output": "This is a 58-year-old male who reports a six to eight-week history of balance problems with fatigue and weakness. He has had several falls recently. He apparently had pneumonia 10 days prior to the onset of the symptoms. He took a course of amoxicillin for this. He complained of increased symptoms with more and more difficulty with coordination. He fell at some point near the onset of the symptoms, but believes that his symptoms had occurred first. He fell from three to five feet and landed on his back. He began seeing a chiropractor approximately five days ago and had adjustments of the neck and lumbar spine, although he clearly had symptoms prior to this. He has had mid and low back pain intermittently. He took a 10-day course of Cipro believing that he had a UTI. He denies, however, any bowel or bladder problems. There is no incontinence and he does not feel that he is having any difficulty voiding."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Have you had any illnesses in the past? \r\nPatient: Nope.\r\nDoctor: Anything that is worth mentioning?\r\nPatient: Nope.\r\nDoctor: Sure?\r\nPatient: Yes.",
      "output": "Noncontributory."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Good afternoon, sir. My nurse tells me you're twenty eight years old, is that correct? \r\nPatient: Good morning, doctor. Yes, that's correct. \r\nDoctor: So, what happened?\r\nPatient: Well, I punched a wall about three days ago. \r\nDoctor: Which hand is it?\r\nPatient: It's my right hand. \r\nDoctor: Is this your dominant hand?\r\nPatient: Unfortunately, yes, it is. \r\nDoctor: Where does it hurt?\r\nPatient: Um, it's right here on the outside of my hand. \r\nDoctor: What kind of treatments have you had?\r\nPatient: I went to the E D, and they pushed some of the joints in my hand back, and they put me in a splint, so I've been wearing that ever since. \r\nDoctor: How is your pain today? \r\nPatient: Compared to when it started, it's much better today. \r\nDoctor: How would you describe your pain today?\r\nPatient: Today, I'd say it's minimal pain.\r\nDoctor: Good, do you have any numbness or tingling today?\r\nPatient: No, thankfully not.",
      "output": "The patient is a 28-year-old right-hand dominant gentleman, who punched the wall 3 days prior to presentation.  He complained of ulnar-sided right hand pain and was seen in the emergency room.  Reportedly, he had some joints in his hand pushed back and placed by somebody in emergency room.  Today, he admits that his pain is much better.  Currently, since that time he has been in the splint with minimal pain.  He has had no numbness, tingling or other concerning symptoms."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello there, how are you?\r\nPatient: I am good, thank you.\r\nDoctor: He is my colleague Doctor Mason, and he will be assisting me today and taking down notes.\r\nGuest_clinician: Hi there.\r\nPatient: Hello. \r\nDoctor: Is it okay with you if he can join us?\r\nPatient: Sure, no problem. \r\nDoctor: Great, thank you\r\nDoctor: Doctor Mason can you take down the notes.\r\nGuest_clinician: Sure.\r\nDoctor: Patient looks well developed and well nourished. He is alert with not acute distress. \r\nGuest_clinician: Got it.\r\nDoctor: Patient had a head injury, but he is fully conscious. G C S is fifty and nontoxic. \r\nGuest_clinician: Okay.",
      "output": "GENERAL: Well developed, well nourished, alert, in no acute distress.  GCS 50, nontoxic."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Anyone sick in your family?\r\nPatient: No.\r\nDoctor: How about anyone with the same disorders?\r\nPatient: No, I don't know.\r\nDoctor: Okay don't you worry.",
      "output": "Noncontributory."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How did the patient do on the activity test?\r\nGuest_clinician: Patient was good. I have advised him to continue with his normal activities as long as he is feeling fine.",
      "output": "As tolerated."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How old was he when he were first evaluated in the other hospital?\r\nGuest_family: He was seven.\r\nDoctor: Which hospital was that again?\r\nGuest_family: It was at U I H C.\r\nDoctor: So what exactly happened? \r\nGuest_family: He was doing all good like seven months before his evaluation, then he started having some dizzy spells, which like stayed for several seconds to a minute. They were not regular, but he was able to continue his activity immediately after these dizzy spells. \r\nDoctor: Did the intensity change? \r\nGuest_family: Oh yes. This, these spells, they became more frequent, and they were now for longer periods. By the time we came for the first evaluation, they were like two to three times per day. \r\nDoctor: How long were they in the duration? \r\nGuest_family: They lasted for like two to three minutes. \r\nDoctor: Was there any other associated disorder or anything? \r\nGuest_family: Yeah, around three months before his evaluation his hands, they started becoming stressed, like stiffer and felt tighter during these spells. He also felt very weak and tired after these episodes.",
      "output": "The patient was initially evaluated at UIHC at 7 years of age. He had been well until 7 months prior to evaluation when he started having spells which were described as \"dizzy spells\" lasting from several seconds to one minute in duration. They occurred quite infrequently and he was able to resume activity immediately following the episodes. The spell became more frequent and prolonged, and by the time of initial evaluation were occurring 2-3 times per day and lasting 2-3 minutes in duration. In addition, in the 3 months prior to evaluation, the right upper extremity would become tonic and flexed during the episodes, and he began to experience post ictal fatigue."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you have major illnesses in the family like diabetes or high B P?\r\nPatient: No nothing. No major illnesses.\r\nDoctor: Okay.\r\nPatient: Yes.",
      "output": "Noncontributory."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Good morning, sir. \r\nPatient: Good morning, doctor. \r\nDoctor: I just need some background information before we begin today. \r\nPatient: Sure. \r\nDoctor: Good, have you ever had surgery, sir? \r\nPatient: Yeah, actually I've had it on my knee, a nose job, and, um, carotid sinus surgery.",
      "output": "Right knee surgery, cosmetic surgery, and carotid sinus surgery."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Are you still working?\r\nPatient: No, I am retired now. I used to work for the U S postal service as an electronic technician but took retirement one year earlier due to my disability.\r\nDoctor: Ah okay. And who is in your family?\r\nPatient: Well, I stay with my wife and daughter in our apartment.\r\nDoctor: Okay. Do you smoke?\r\nPatient: No.\r\nDoctor: How about alcohol? \r\nPatient: I use to drink occasionally, that too very rare, but after my symptoms stated I stopped completely.\r\nDoctor: Any use of recreational or illegal drugs? \r\nPatient: Nope.\r\nDoctor: Did you travel anywhere recently?\r\nPatient: No, it's been really long since I traveled anywhere.",
      "output": "The patient retired one year PTA due to his disability. He was formerly employed as an electronic technician for the US postal service. The patient lives with his wife and daughter in an apartment. He denied any smoking history. He used to drink alcohol rarely but stopped entirely with the onset of his symptoms. He denied any h/o drug abuse. He denied any recent travel history."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Good afternoon, how are you today? \r\nPatient: I am good Doctor, thanks for asking.\r\nDoctor: This is my colleague Doctor White, and she will be taking the notes. Is it okay if she joins us? \r\nPatient: Oh sure, no problem.\r\nDoctor: Thank you.\r\nGuest_clinician: Hello, I am Doctor White, nice to meet you.\r\nPatient: Nice to meet you too.\r\nDoctor: Okay, can you breathe in and out for me? Deep breaths please.\r\nPatient: Okay.\r\nDoctor: Okay breath sounds are clear. Lung function looks good. Symmetrical rise and fall in chest as patient breathes. I am going to palpate your chest, it's just a routine exam.\r\nPatient: Sure.\r\nDoctor: Doctor White can you make a note, no egophony or tactile fremitus.\r\nGuest_clinician: Sure.",
      "output": "RESPIRATORY: Good respiratory effort.  Clear to auscultation.  Clear to percussion.  Chest:  Symmetrical rise and fall.  Symmetrical expansion.  No egophony or tactile fremitus."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Where do you live?\r\nPatient: I live in a board and care. It is a nice small care home with some very nice and supportive people. It is just next to the Safeway on Village Drive. \r\nDoctor: Nice. It looks like you love living there. \r\nPatient: Oh yes. I feel very relaxed there. \r\nDoctor: Did you consume alcohol in any way? \r\nPatient: No Sir. \r\nDoctor: Any tobacco consumption? \r\nPatient: Never in my life. \r\nDoctor: Did you ever try any kind of illicit drugs? Any I V drugs? \r\nPatient: No. I have always kept myself away from all those things.",
      "output": "The patient lives in a board and care.  No tobacco, alcohol or IV drug use."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Have you had any surgeries in the past?\r\nPatient: Actually, yes, I had my gallbladder removed in nineteen ninety two.\r\nDoctor: Great, any other surgeries? Think back a little further? \r\nPatient: Oh yeah, I had my appendix out in nineteen eighty eight.",
      "output": "Appendectomy 1988. Cholecystectomy. 1992"
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How are feeling now after the treatment?\r\nPatient: I am feeling pretty fair, improving slowly.\r\nDoctor: Okay?\r\nPatient: Okay.",
      "output": "Fair, but improved."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Sir? Can you hear me? Are you Mister Smith's wife? \r\nGuest_family: Yes. I am his wife. \r\nDoctor: How old is he? Can you tell me a little bit of how your husband's condition has come to this point? His level of consciousness is concerning. \r\nGuest_family: He is eighty five. He took the entire M G of Xanax. He is only supposed to take point one twenty five M G of Xanax.  That is why he is like this.  \r\nDoctor: It looks like your husband was admitted to the emergency room the night before.  How did these injuries to his face happen? \r\nGuest_family: He fell off his wheelchair.  \r\nDoctor: The Adult Protective Services said they found your husband in the home barley conscious. How long had he been that way? \r\nGuest_family: All day. \r\nDoctor: Do you know what other medications your husband has taken other than the Xanax?  \r\nGuest_family: He didn't take his regular medications for two days.",
      "output": "The patient is an 85-year-old male who was brought in by EMS with a complaint of a decreased level of consciousness.  The patient apparently lives with his wife and was found to have a decreased status since the last one day.  The patient actually was seen in the emergency room the night before for injuries of the face and for possible elderly abuse.  When the Adult Protective Services actually went to the patient's house, he was found to be having decreased consciousness for a whole day by his wife.  Actually the night before, he fell off his wheelchair and had lacerations on the face.  As per his wife, she states that the patient was given an entire mg of Xanax rather than 0.125 mg of Xanax, and that is why he has had decreased mental status since then.  The patient's wife is not able to give a history.  The patient has not been getting Sinemet and his other home medications in the last 2 days."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How have you been feeling? Is the Wellbutrin keeping your mood stabilized? \r\nPatient: I have been feeling good. The Wellbutrin is working well for me.  \r\nDoctor: It is important to not consume any alcohol or recreational drugs while taking Wellbutrin.  \r\nPatient: I don't drink or do drugs.",
      "output": "The patient has a history of depression.  No history of substance abuse."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Tell me a little bit about your family history. \r\nPatient: My dad and grandpa both had type two diabetes. My son is struggling with type one diabetes at the moment.  \r\nDoctor: I'm sorry to hear that. Does anyone in your family have heart problems? \r\nPatient: No. \r\nDoctor: How about cancer? \r\nPatient: Two of my cousins had breast cancer.",
      "output": "As far as heart disease there is none in the family.  As far as cancer two cousins had breast cancer.  As far as diabetes father and grandfather had type II diabetes.  Son has type I diabetes and is struggling with that at the moment."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Where do you work, miss? \r\nPatient: Well, you see, I am a civil engineer. Right now, due to pandemic like everyone else I am working from home. \r\nDoctor: Are you working full time or is your disability affecting that?\r\nPatient: No, I can only work on half time. This disability does not let me work full time. I need to go to physical therapy quite frequently on and off and I also have a baby who consumes a lot of my time. \r\nDoctor: Do you smoke or drink? \r\nPatient: No, I've never done any of them.",
      "output": "The patient is a civil engineer, who currently works from home.  She is working approximately half time because of limitations imposed on her by her disability, need to attend frequent physical therapy, and also the needs of looking after her baby.  She does not smoke and does not drink and has never done either."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you know any familiar diseases in your family? \r\nPatient: Do you mean like B P, high sugar? \r\nDoctor: Yes.\r\nPatient: No, no one in my family has anything like that.\r\nDoctor: Great.",
      "output": "Noncontributory."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Have you had any anxiety attacks lately? \r\nPatient: No.\r\nDoctor: Have you felt depressed or had any mood swing problems? \r\nPatient: No.\r\nDoctor: Any phobias?\r\nPatient: No, not really. \r\nDoctor: Okay.",
      "output": "PSYCHIATRIC: Normal; Negative for anxiety, depression, or phobias."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you have a history of mental illness or psychological disease? \r\nPatient: No.",
      "output": "None Past Psychological History: None"
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello sir. How are you doing today? You still look a little uncomfortable. Is there still pain?\r\nPatient: Yeah. Still a good amount of pain. I did not take my pain medication this morning though. Not sure if that will make a huge difference. \r\nDoctor: That is possibly why you are still in pain. How is movement? Can you get out of the house and get around?\r\nPatient: Yes. I am quite happy that I can do my daily activities. I can get up with minimal assistance and do many activities out of the house. I think I am gaining muscle from moving around more too. \r\nDoctor: How is the home exercise program going?\r\nPatient: I am loving pool therapy. I really feel like that is helping. I do the home exercises sometimes twice a day. I really want to get back to normal.",
      "output": "The patient states pain still significant, primarily 1st seen in the morning.  The patient was evaluated 1st thing in the morning and did not take his pain medications, so objective findings may reflect that.  The patient states overall functionally he is improving where he is able to get out in the house and visit and do activities outside the house more.  The patient does feel like he is putting on more muscle girth as well.  The patient states he is doing well with his current home exercise program and feels like pool therapy is also helping as well."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Have you had any surgeries in the past?\r\nPatient: Yes, I had knee surgery.\r\nDoctor: Which knee?\r\nPatient: Right.",
      "output": "Right knee surgery."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Are you sexually active? \r\nPatient: Yes. \r\nDoctor: How many partners do you have? \r\nPatient: Just one. \r\nDoctor: Is this a monogamous relationship? \r\nPatient: Yes. \r\nDoctor: What gender is you partner? \r\nPatient: He is a male. We have been together for three years. He is H I V positive.",
      "output": "Homosexual, in monogamous relationship with an HIV infected partner for the past 3 years."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: I remember you mentioned that you had one operation done in the past. \r\nPatient: I had a lymph node biopsy back in September of O three. \r\nDoctor: Did it come back negative? \r\nPatient: Fortunately, yes.",
      "output": "Excisional lymph node biopsy (9/03)."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: It looks like you have an extensive medical history. \r\nPatient: I blame my heart. It's caused me the most trouble. I had coronary artery bypass surgery in twenty ten along with an angioplasty. \r\nDoctor: I'm sorry that your heart has been giving you so much trouble. I'm happy that you're here with us today and taking the right measures to keep yourself healthy. \r\nPatient: Oh, and I forgot to mention that I've had prostate biopsies in the past. \r\nDoctor: When did you have the biopsies done? \r\nPatient: Last year. \r\nDoctor: Did they come back negative? \r\nPatient: Yes, fortunately. I guess my prostate isn't as troublesome as my heart. \r\nDoctor: I understand.",
      "output": "Coronary artery bypass surgery and a prior angioplasty and prostate biopsies."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you have any medical problems? \r\nPatient: Let's see. I have diabetes, high blood pressure, high cholesterol, and osteoporosis.  \r\nDoctor: And any surgeries? \r\nPatient: Several. \r\nDoctor: Which ones? \r\nPatient: I had my tonsils taken out when I was a kid. I also had my uterus removed along with my ovaries and fallopian tubes. The list goes on. I had my appendix removed and two or three of my parathyroids taken out. Despite getting some of my parathyroids removed, I still have borderline high calcium levels according to my endocrinologist. \r\nDoctor: Did you experience any complications during or after surgery? \r\nPatient: No. I forgot to mention that I had two carpel tunnel releases as well.",
      "output": "She has also had a hysterectomy, salpingoophorectomy, appendectomy, tonsillectomy, two carpal tunnel releases.  She also has had a parathyroidectomy but still has had some borderline elevated calcium.  Also, hypertension, hyperlipidemia, as well as diabetes.  She also has osteoporosis."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: What is your family medical history? \r\nPatient: My mother passed away from complications with Huntington Disease. She was diagnosed and had been having treatments at U I H C. My grandmother and two of my aunts also passed away from Huntington as well. \r\nDoctor: I am so sorry. Do you have siblings?\r\nPatient: Yes! I have one sister. She is thirty eight. She has a lot of metal issues. She has attempted suicide two times. \r\nDoctor: Are you close with her? \r\nPatient: No. Not really. \r\nDoctor: Are you married? \r\nPatient: Yes.\r\nDoctor: Do you have children? \r\nPatient: Yes. We have two adopted kids.",
      "output": "Mother died age 60 of complications of Huntington Disease (dx at UIHC). MGM and two MA's also died of Huntington Disease. His 38 y/o sister has attempted suicide twice. He and his wife have 2 adopted children."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Any medical problems on your mom or dad's side? \r\nPatient: My dad has lupus and his brother has Addison's disease. High blood pressure also runs in the family. \r\nDoctor: Is your dad being treated for lupus? \r\nPatient: Yes, he follows up with his rheumatologist pretty regularly.",
      "output": "HTN, father with SLE, uncle with Addison's Disease."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: I will do a quick exam on you.\r\nPatient: What kind of exam? \r\nDoctor: I'm just checking for lymph nodes. Whenever there is an infection those guys are the first ones to be noticed with swelling.\r\nDoctor: Okay, so let's first check your neck area. It looks good. I don't feel any inflamed lymph node. Your armpits look good too and the last place to check is your groin area. It is all good. No sign of infection.",
      "output": "LYMPH: No neck, axillary or groin adenopathy was noted."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: What are some medications you are on?\r\nPatient: I am on pain pills.\r\nDoctor: Do you know their names?\r\nPatient: Yes. Oxycontin and Vicodin.\r\nDoctor: Okay that helps.",
      "output": "OxyContin and Vicodin."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: I am looking at the list of your medication.\r\nPatient: Okay.\r\nDoctor: All I can see is Risperdal and Invega.\r\nPatient: I think that is correct.\r\nDoctor: Are you not taking anything else?\r\nPatient: Yes, I take some multivitamins, but do I need to mention it?\r\nDoctor: Yes, you should. We need to know everything.\r\nPatient: Okay.",
      "output": "Listed as Invega and Risperdal."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Good morning, ma'am. \r\nPatient: Oh, good morning, doctor. \r\nDoctor: Please, tell me about your living situation. \r\nPatient: Well, right now, I live at home with my kids and my dad. \r\nDoctor: I see here that you're not able to go up the stairs well, can you tell me more about that?\r\nPatient: Yeah, I can't use the stairs without holding the rail the entire time. \r\nDoctor: Holding the rail makes navigating the stairs easier? \r\nPatient: Yeah, but I still move very slow. \r\nDoctor: I see. Do you smoke?\r\nPatient: Yeah, I smoke about a pack to a pack and a half a day. \r\nDoctor: What about exercise? Do you workout? \r\nPatient: No, I don't regularly workout, I've never been good at it.",
      "output": "The patient lives in a private home with children and her father.  The patient states that she does have stairs to negotiate without the use of a railing.  She states that she is able to manage the stairs, however, is very slow with her movement.  The patient smokes 1-1/2 packs of cigarettes a day and does not have a history of regular exercise routine."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Patient: My physician did a blood test. My potassium is high. He recommended me to meet you.\r\nDoctor: Okay. I did not get the blood report yet. I am waiting for your doctor's office to send it to me. Is it only your potassium that is elevated?\r\nPatient: Yes, that's what they told me.",
      "output": "\"My potassium is high\""
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Guest_family: He was going to buy me a surprise but met with this car accident.\r\nDoctor: I am sorry! He does have multiple trauma due to the accident, and he will require aftercare. \r\nGuest_family: Yeah.",
      "output": "Aftercare of multiple trauma from an motor vehicle accident."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: So, what is your family's living situation at home?\r\nGuest_family: Um, he lives at home with me, and his father. \r\nDoctor: May I assume that you are his biological parents? \r\nGuest_family: Yes, that's correct. \r\nDoctor: Great, does he have any siblings? \r\nGuest_family: No, right now, he's an only child. \r\nDoctor: What grade is he in? \r\nGuest_family: He's in the third grade. \r\nDoctor: Great, and is he doing well in school? \r\nGuest_family: Yes, he's doing quite well.",
      "output": "lives with biologic father and mother. No siblings. In 3rd grade (mainstream) and maintaining good marks in schools."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Good afternoon, what gender do you identify with?\r\nPatient: Thank you for asking, I identify as a female.\r\nDoctor: Thank you. Do you know of any chronic illnesses?\r\nPatient: No, but can you give me some examples of what you mean?\r\nDoctor: Well, high blood pressure, osteoarthritis, diabetes, depression, anything like that ring any bells?\r\nPatient: Oh, no, I don't have anything like that.",
      "output": "She claims no chronic illnesses."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you have any major medical conditions that I should know about? \r\nPatient: What, like cancer? \r\nDoctor: It doesn't have to be that serious, but is there anything you take medicine for? \r\nPatient: Oh, I have allergies and asthma.",
      "output": "Asthma and allergies."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Can you tell me something about your mom and dad?  Like any diseases they have had?\r\nPatient: Sure, my dad died of heart attack when he was sixty five and my mom died of stroke when she was seventy.\r\nDoctor: How's about siblings, miss? Any health issues?\r\nPatient: No, my brother is healthy.",
      "output": "Basically unchanged.  Her father died of an MI at 65, mother died of a stroke at 70.  She has a brother, healthy."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Does anyone in your family suffer from any health problems? \r\nPatient: No one comes to mind. \r\nDoctor: Great.",
      "output": "Negative."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Tell me, what's going on? \r\nGuest_family: She is complaining of weakness on the right side of her face.\r\nPatient: And I feel the right side is drooping.\r\nDoctor: Okay, let me look at it.",
      "output": "Right-sided facial droop and right-sided weakness."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: My chart here says that you're eighty three years old, is that correct, ma'am? \r\nPatient: Yes doctor, that's correct, I just had my birthday. \r\nDoctor: Happy belated birthday! How have you been doing since your last visit?\r\nPatient: Well, my cancer hasn't needed phlebotomies for several months now, which is good. \r\nDoctor: That's great, you have been treated for polycythemia vera, correct? \r\nPatient: Yes, that's the one. \r\nDoctor: I also see you're unassisted today, which is also great. \r\nPatient: Yeah, having some independence is nice.",
      "output": "The patient is an 83-year-old female with a history of polycythemia vera.  She comes in to clinic today for followup.  She has not required phlebotomies for several months.  The patient comes to clinic unaccompanied."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: So, do you have any family history of cancer?\r\nPatient: Well, yes, but I can't remember who had what kind. \r\nDoctor: Still, that's helpful, thank you. What about heart disease?\r\nPatient: That too, there's some history of heart disease, but I can't remember who.",
      "output": "1.  Cancer. 2.  Coronary artery disease."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: As far as you know, are there any major health conditions that you know about? \r\nPatient: What do you mean by that? \r\nDoctor: Anything like cancer, or arthritis, do those sound familiar?\r\nPatient: Oh, um, no nothing like that.",
      "output": "Otherwise, negative."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you have any medical history that we should be aware of? \r\nPatient: I have type two diabetes. My numbers always come high.\r\nDoctor: Okay, anything else? \r\nPatient: I also have high cholesterol.\r\nDoctor: Okay.",
      "output": "Diabetes type II, poorly controlled, high cholesterol."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello. How are you feeling today? \r\nPatient: Great. I'm just here for my yearly physical. \r\nDoctor: Oh, good. I see your past medical history is missing. Do you, by chance, know if you've had any health related problems before? \r\nPatient: Uhm. Let me check my notes on my phone. I knew this question would pop up, but I always forget. Oh, perfect. You can take a look at them. \r\nDoctor: Thank you. I just want to verify the information with you. You had asthma, nasal inflammation, and some abnormal growth on you neck, correct? \r\nPatient: If it's on there, then it's true. I usually don't remember these kinds of things. My wife is usually here with me. She knows all about my health.",
      "output": "Significant for asthma, allergic rhinitis and cervical dysplasia."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How's the little one doing?\r\nGuest_family: She is doing okay. \r\nDoctor: How long was your pregnancy?\r\nGuest_family: Thirty six weeks.\r\nDoctor: Was your delivery normal or C section?\r\nGuest_family: It was a C section. \r\nDoctor: How much did she weigh? \r\nGuest_family: She was eight pounds and three ounces.\r\nDoctor: Tell me what's the issue?\r\nGuest_family: Yeah, she has a history of seizures. It looks like she is having pain in her tummy and is throwing up. \r\nDoctor: What else did you notice?\r\nGuest_family: It looks like she is having some rashes on her skin. There is vomiting for sure. She also feels bloated. She also complains of pain in her tummy. Sometimes she does scratch her mouth. We also noticed some swelling around her lips, eyes and face.\r\nDoctor: It looks like she's having some food intolerance.",
      "output": "Born at 36 weeks' gestation by C-section delivery at 8 pounds 3 ounces.  She does have a history of febrile seizures and what parents reported an abdominal migraine, but on further questioning, it appears to be more of a food intolerance issue."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: What medications are you taking right now?\r\nPatient: I am taking Advair and Allegra.\r\nDoctor: Okay is it helping you?\r\nPatient: I don't know, I am not sure the Allegra is helping. But I do take them regularly.\r\nDoctor: But is it like better than Claritin?\r\nPatient: Yes, I think so.\r\nDoctor: Okay that's good.\r\nPatient: Shall I continue?",
      "output": "Advair and Allegra.  He has been taking these regularly.  He is not sure the Allegra is working for him anymore.  He does think though better than Claritin."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Anybody sick in family?\r\nPatient: No one.\r\nDoctor: How about any illnesses that run in your family?\r\nPatient: No, everyone is healthy.",
      "output": "Noncontributory."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hi again! How has your acne been since you started the spironolactone? \r\nPatient: It has been improving.  \r\nDoctor: Have you experienced any increased thirst, mood changes or unusual fatigue? \r\nPatient: No.",
      "output": "The patient comes for a routine followup appointment."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Well, I don't think you need any restraints as you are doing fine. I do want to make sure you have a chair and bed monitor since you have a history of multiple falls. They can help detect fall. \r\nPatient: I don't want that, I will manage. \r\nDoctor: Are you sure?\r\nPatient: Yes!",
      "output": "RESTRAINTS: None.  The patient has declined use of chair check and bed check."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you know when was the last time you got a tetanus shot?\r\nPatient: No I don't remember.\r\nDoctor: Okay.",
      "output": "Not sure."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hi there! How are you today? \r\nPatient: Hi! I am good. \r\nDoctor: Welcome in! \r\nPatient: Thank you. \r\nDoctor: Lets start with a little social history. Are you a tobacco or alcohol user? \r\nPatient: No. \r\nDoctor: Are you married? Do you have children? \r\nPatient: I am not married but I do have a two year old son. \r\nDoctor: Do you currently see a gynecologist? \r\nPatient: Yes. She is in Bartow. \r\nDoctor: Great.",
      "output": "She is followed by a gynecologist in Bartow.  She is not an alcohol or tobacco user.  She is not married.  She has a 2-year-old child."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Tell me about your family medical history. \r\nPatient: My family is pretty healthy. I don't know of any health problems.",
      "output": "Noncontributory."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Welcome in. \r\nPatient: Thank you. \r\nDoctor: Do you smoke? \r\nPatient: No, I don't. Smoking is gross. \r\nDoctor: I agree. Do you drink alcohol?\r\nPatient: Yes. \r\nDoctor: How much do you drink per day or week? \r\nPatient: When I get off work usually have a glass of wine. I don't ever have more then one glass. \r\nDoctor: Okay.",
      "output": "She does not smoke.  She takes one glass of wine per day."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: The nurse applied antibiotic ointment and a bandage to your foot. Did she go over how to change the bandage at home? \r\nPatient: Yes.",
      "output": "The patient had antibiotic ointment and a bandage applied to his foot."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello. Before we begin, I need you to confirm some information for me. \r\nPatient: What kind of information? \r\nDoctor: About your family. Do you know if you have certain medical conditions that run in your family? \r\nPatient: Nope. My family is very healthy.",
      "output": "Negative."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How about any breathing issues or asthma?\r\nPatient: Actually, I have a history of asthma.\r\nDoctor: Oh okay, and was it severe or mild?\r\nPatient: Well, it was not severe but still remarkable.\r\nDoctor: Hm, alright.  Anything else?\r\nPatient: Yes, I also struggled with a serious acne problem.\r\nDoctor: Got it.",
      "output": "Significant for asthma and acne."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: How's she doing? \r\nGuest_family: She's had better days. \r\nDoctor: Aw and why's that? \r\nGuest_family: She's been really congested recently. Snorting a lot more, too. She's onlt eleven and I think it is odd she snores so much. I took her to see the allergist and he said it's not her allergies so we stopped giving her Allegra. \r\nDoctor: Does she happen to snore at night? \r\nGuest_family: No, not really. \r\nDoctor: Hm. \r\nGuest_family: And while we're here, I also wanted you to check out her toe. The right big toe appears a bit red to me. The skin around it has been peeling for the last week and a half. \r\nDoctor: Lemme take a look. Have you applied anything to the area?",
      "output": "This is an 11-year-old female who comes in for two different things.  1.  She was seen by the allergist.  No allergies present, so she stopped her Allegra, but she is still real congested and does a lot of snorting.  They do not notice a lot of snoring at night though, but she seems to be always like that.  2.  On her right great toe, she has got some redness and erythema.  Her skin is kind of peeling a little bit, but it has been like that for about a week and a half now."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Why are you holding your face?\r\nPatient: Ah! Have pain in my tooth.\r\nDoctor: Oh, how bad is it?\r\nPatient: Oh, awfully bad.\r\nDoctor: I am so sorry.",
      "output": "Toothache."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Have you had similar symptoms before? \r\nPatient: No never like this.\r\nDoctor: Any other complaints you have had in the past?\r\nPatient: Just some knee pain issues.\r\nDoctor: Okay, so chronic knee pain.\r\nPatient: Yes.",
      "output": "Chronic knee pain."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Can you tell me about any cancers in your family?\r\nPatient: Yes, my sister has ovarian cancer, and my father has liver cancer.\r\nDoctor: Oh I am so sorry.\r\nPatient: That is okay.\r\nDoctor: Any heart conditions?\r\nPatient: My mom and dad both have heart disease. My dad has diabetes too.",
      "output": "Consistent with a sister of his has ovarian cancer and his father had liver cancer.  Heart disease in the patient's mother and father, and father also has diabetes."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor:  Can you tell me what problems you have had in the past. Or what medical issues are currently going on?\r\nPatient: You mean my heart problem and things?\r\nDoctor: Yes.\r\nPatient: Okay, I have hypertension and kidney problems since many years.\r\nDoctor: Okay.\r\nPatient: I get frequent urinary infections.\r\nDoctor: Your urine creatinine is normal.\r\nPatient: Okay. I also have severe aortic stenosis.",
      "output": "Significant for moderate to severe aortic stenosis, urinary tract infection, hypertension, chronic kidney disease (although her creatinine is near normal)."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Does anyone else in your family have aneurysm problem?\r\nPatient: Well, my grandmother had it. She actually passed away due to brain aneurysm. \r\nDoctor: Oh, okay.",
      "output": "Grandmother died of cerebral aneurysm."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: What is wrong with your back honey?\r\nPatient: Oh, it all started off with a little pimple on the buttock.  I was soaking it at home with hot water and stuff, but it did not improve. I hope this is not cancer. I am only twenty four. \r\nDoctor: Okay what exactly are you experiencing?\r\nPatient: I have pain.\r\nDoctor: So you came to the hospital on the first and they did an I and D in E D?\r\nPatient:   Yes I was admitted to the hospitalist service with high blood sugars. My African American father was so scared. \r\nDoctor: Okay sugars high. Do you know the number? How high?\r\nPatient: No, I do not know that but they found positive bacteria or some sort of thing in my blood culture. \r\nDoctor:  So today we are evaluating you for surgery?\r\nPatient: Yes.",
      "output": "This patient is a 24-year-old African-American female who presented to the hospital with buttock pain.  She started off with a little pimple on the buttock.  She was soaking it at home without any improvement.  She came to the hospital on the first.  The patient underwent incision and drainage in the emergency department.  She was admitted to the hospitalist service with elevated blood sugars.  She has had positive blood cultures.  Surgery is consulted today for evaluation."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hi there! I have the results from your ultrasound. You have kidney stones in the ureter close to the bladder.\r\nPatient: Oh no. \r\nDoctor: This explains the pain you have been having on your left side. Are you still experiencing nausea and vomiting? \r\nPatient: Yes, I have been. \r\nDoctor: I would like to set you up with a consult with a consult with a surgeon.\r\nPatient: Okay.",
      "output": "1.  Left flank pain. 2.  Left ureteral stone. 3.  Nausea and vomiting."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Any known drug allergies? \r\nPatient: No.",
      "output": "No known drug allergies."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Your daughter had an exposure to the ant bait but we are not sure if she actually ingested any of it. Poison Control confirmed that even if she did ingest the small amount that she was found with, it is likely nontoxic. Do you have any questions? \r\nGuest_family: No.",
      "output": "Exposure to ant bait."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hello, sir. How are you today?\r\nPatient: I am alright. I am here for a check up since I am feeling kind of dizzy lately. \r\nDoctor: That is not good. How long has this been happening?\r\nPatient: A few months. This happened to my sister too. I think she is still dealing with it. \r\nDoctor: Is there any other family medical history I should know about? Migraines or cancer?\r\nPatient: No. Not that I know of. The rest of my family seems pretty healthy.",
      "output": "Sister is dizzy but no other acute illnesses."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Do you know anyone in your family whose had cancer? \r\nPatient: No one that I know.",
      "output": "Negative for cancer."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Okay so your blood report is back and the cardiac enzyme we were looking for are negative. \r\nPatient: Okay.\r\nDoctor: Your blood urea nitrogen, also known as B U N, is within normal limits and hydrogen is stable. Creatinine is also within the normal range.\r\nPatient: Great!",
      "output": "First set of cardiac enzyme profile negative.  H&H stable.  BUN and creatinine within normal limits."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Are you on any medications?\r\nPatient: No, not taking any medications.",
      "output": "None."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Hi, how are you doing today? \r\nPatient: I've been better. Thank you. \r\nDoctor: So, you are here for your follow up right? Remind me how often are you coming here? \r\nPatient: That's right. I'm coming around between a month or two. \r\nDoctor: Yeah, it's every four to eight weeks. \r\nPatient: I'm not taking any medicine now. I just wanted to let you know. \r\nDoctor: Yeah, I can see it in your record. It says that you are off of all the immunosuppression. So, just let me check. It says here that you do have mild chronic G V H D. It is not that bad that I should be worried about any therapy or anything else. How long ago did you get that transplant? \r\nPatient: I think it was around four and a half years ago. I'm feeling much better after that. I do have complaints of blood in my stool. But after you sent me to that doctor, that gastro doctor, I feel good. I know they said that they removed something, but I'm not sure, but after that it has been improved a lot. \r\nDoctor: Okay, let me see in my chart. You had some rectal bleeding issues because of which I referred you to the gastroenterologist. A complete endoscopy was performed, which was both on the upper and the lower side. There was no evidence of ulcers or any other abnormality. That's  good news, right? \r\nPatient: Yeah, I agree. That was a relief. \r\nDoctor: They did find some polyps and they removed it. They turned out to be benign, so nothing to worry about there. \r\nPatient: Yeah, I remember this said they removed something, but I forgot the name. \r\nDoctor: Is there any other issue that I can help you with? \r\nPatient: I don't know. I feel a lot of fatigue and like I'm not able to do things like I used to do before. I get tired very easily. I don't know if it is related to something or not, but things have been weird. I'm not able to do even the minor things like I lift two boxes and I'm done for the day. Is it something that I should be worried about? \r\nDoctor: It looks like you have a mild iron deficiency. I will work on that with you, don't worry.",
      "output": "The patient comes to the clinic today for followup.  I am seeing him once every 4 to 8 weeks.  He is off of all immunosuppression.  He does have mild chronic GVHD but not enough to warrant any therapy and the disease has been under control and he is 4-1/2-years posttransplant. He has multiple complaints.  He has had hematochezia.  I referred him to gastroenterology.  They did an upper and lower endoscopy.  No evidence of ulcers or any abnormality was found.  Some polyps were removed.  They were benign.  He may have mild iron deficiency, but he is fatigued and has several complaints related to his level of activity."
    },
    {
      "instruction": "Summarize the following doctor-patient dialogue into a clinical note.",
      "input": "Doctor: Are you feeling any pain?\r\nPatient: No, I feel great. \r\nDoctor: Is there any other medical issue that we should be worried about? \r\nPatient: No, it feels like I'm young again. I'm able to do all my activities.",
      "output": "COMPLICATIONS: None."
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
