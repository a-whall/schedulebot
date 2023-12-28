import argparse
from dotenv import load_dotenv
import json
import os
import spacy
from spellchecker import SpellChecker
from transformers import (
    pipeline,
    AutoTokenizer,
    T5ForConditionalGeneration,
    AutoModelForQuestionAnswering
)
from sentence_transformers import (
    SentenceTransformer,
    util
)



load_dotenv()
league_entities = os.getenv('LEAGUE_ENTITIES').split(',')

spell_checker = SpellChecker()
language_model = spacy.load('en_core_web_sm')

# TODO: For efficiency, store model output embeddings, not the raw strings.
phrases = {
    "greeting": [
        "Hi.",
        "What's up.",
        "Good day.",
        "Hello.",
        "Yo."
    ],
    "suggestion": [
        "How about next Monday at 3 PM?",
        "Can we meet on Friday morning?",
        "Is Wednesday at 10 o'clock good for you?",
        "Let's schedule it for Tuesday afternoon.",
        "I'm available this Thursday at 2 PM, does that work?"
    ],
    "availability_request": [
        "When are you free to meet?",
        "What times do you have open?",
        "Can you suggest a suitable time?",
        "Tell me your available slots.",
        "Do you have time this week?"
    ],
    "confirmation": [
        "Sounds good.",
        "Sure.",
        "Yeah.",
        "Yes.",
        "That time works for me.",
        "I'm okay with the proposed schedule.",
        "Yes, let's lock in that time.",
        "I agree with your time suggestion.",
        "That schedule is perfect for me."
    ],
    "rescheduling": [
        "Can we move it to a different day?",
        "I need to reschedule our meeting.",
        "That time doesn't work for me, how about another?",
        "Is it possible to change the meeting time?",
        "I have to push our meeting to a later time."
    ]
}



def main(args):

    # Grammar Correction: get grammar-corrected content
    gc_model = T5ForConditionalGeneration.from_pretrained(args.gc_model_name)
    gc_toker = AutoTokenizer.from_pretrained(args.gc_model_name)
    gc_model_input_ids = gc_toker(f"Fix the grammar: {args.content}", return_tensors="pt").input_ids
    gc_model_outputs = gc_model.generate(gc_model_input_ids, max_length=256)
    gc_content = gc_toker.decode(gc_model_outputs[0], skip_special_tokens=True)

    # Paraphrase Detection
    pd_model = SentenceTransformer(args.pd_model_name)
    input_embedding = pd_model.encode(gc_content, convert_to_tensor=True)
    category_similarities = {category: util.cos_sim(input_embedding, pd_model.encode(sentences, convert_to_tensor=True)).mean().item() for category, sentences in phrases.items()}

    # Spelling Correction: it's possible that the grammar correction model missed some words.
    doc = language_model(gc_content)
    misspelled_words = {token.text: spell_checker.correction(token.text) for token in doc if token.text not in spell_checker and not token.is_punct}

    # NLP Attributes
    has_date = any(ent.label_ in ['DATE'] for ent in doc.ents)
    has_time = any(ent.label_ in ['TIME'] for ent in doc.ents)
    is_wh_question = doc[0].text.lower() in ['who', 'what', 'where', 'when', 'why', 'how']
    has_auxiliary_verb = doc[0].tag_ in ['MD', 'VBZ', 'VBP']
    has_inversion = False
    for token in doc:
        if token.dep_ == 'aux':
            for child in token.head.children:
                if child.dep_ in ['nsubj', 'nsubjpass', 'csubj', 'csubjpass', 'expl'] and child.i > token.i:
                    has_inversion = True

    # Question Answering for 
    affirmative_context = 'Nothing is up.\nWe are available Tuesday any time.\nWe are available Wednesday at 5.\nWe are available Friday at 9.'
    negative_context = 'We are unavailable thursday.'

    qa_pipeline = pipeline('question-answering', model=args.qa_model_name, tokenizer=args.qa_model_name)

    response = None

    negative = qa_pipeline({ 'question': gc_content, 'context': negative_context })
    if negative['score'] > 0.1: #or not date_matches_answer:
        # suggest a different time
        response = negative['answer']

    affirmative = qa_pipeline({ 'question': gc_content, 'context': affirmative_context })
    if affirmative['score'] > 0.1:
        if response is None:
            response = affirmative['answer']

    if response is None:
        response = "Not sure, let me check with the dads"

    output = {
        'has_date': has_date,
        'has_time': has_time,
        'is_wh_question': is_wh_question,
        'has_auxiliary_verb': has_auxiliary_verb,
        'has_inversion': has_inversion,
        'question': gc_content,
        'response': response,
        'score': f"(+{affirmative['score']:.2f}, -{negative['score']:.2f})",
        'uncorrected_words': misspelled_words,
        'action_category_score': category_similarities
    }
    print(json.dumps(output))

    

# Conversation Actions:
# - Date/Time Suggestion
# - Date/Time Request
# - Date/Time Constraint
# - Date/Time Confirmation
# - Date/Time Denial
# - Other

# Team Control Actions:
# - /Schedule
# - Modify poll Date/Time

# States:
# - Initiated: Someone on our team has invoked `/schedule user` and the bot has sent a message starting the scheduling conversation asking for Suggestion or Request.
# - Polling: The bot is waiting on the results of a poll in #scheduling channel.
# - Awaiting: The bot is waiting on the response of another team.

def conversation_state(state, action, last_poll=None):
    """ Returns indicator for what type of response the model should generate """

    if state == "initiated":
        if action == "suggestion":
            # print("Assess the suggestion using the qa model pipeline")
            return "qa"
            # if negative context match:
                # Find closest day not in negative context to make a suggestion
            # else check affirmative context match:
                # 
        elif action == "request":
            print("Randomly sample a time from affirmative context to suggest")
            print("Make a poll in scheduling with sampled time")
            return "poll"
        else:
            print("response type not implemented")
            return "initiated"

    elif state == "Polling":
        if action == "Passes":
            print("Send Message requesting confirmation")
            return "Awaiting"
        if action == "Fails":
            return conversation_state("Ready", "Begin")

    elif state == "Awaiting":
        if action == "Confirm":
            print('Sending Message "see you then"')
            print("Create server event, auto-interest those who confirmed")
            return "Scheduled"
        if action == "Denied":
            return conversation_state("Ready", "Begin")

    return state



if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=
        """
        Discord chat bot program for scheduling.
        """
    )

    parser.add_argument(
        "--content",
        type=str,
        help="The message content to process.",
        metavar=""
    )

    parser.add_argument(
        "--state",
        type=str,
        help="The state of the scheduling conversation.",
        metavar=""
    )

    parser.add_argument(
        "--qa_model_name",
        type=str,
        help="The name of the pre-trained Question-Answering model to load. This model is used to get answers to scheduling queries.",
        default="deepset/roberta-base-squad2",
        metavar=""
    )

    parser.add_argument(
        "--gc_model_name",
        type=str,
        help="The name of the pre-trained grammar fixing model to load. This model is used to correct informal text from conversation which is needed because the other models were trained on formal text.",
        default="grammarly/coedit-large",
        metavar=""
    )

    parser.add_argument(
        "--pd_model_name",
        help="The name of the pre-trained paraphrase detection model to load. This model is used to classify the goal of the user message content.",
        default="all-MiniLM-L6-v2",
        metavar=""
    )

    main(parser.parse_args())
