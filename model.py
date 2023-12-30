import argparse
from dotenv import load_dotenv
import json
import os
import re
from sentence_transformers import (
    SentenceTransformer,
    util
)
import spacy
from spellchecker import SpellChecker
from transformers import (
    pipeline,
    AutoTokenizer,
    T5ForConditionalGeneration,
    AutoModelForQuestionAnswering
)
import torch



load_dotenv()
league_entities = os.getenv('LEAGUE_ENTITIES').split(',')

spell_checker = SpellChecker()
language_model = spacy.load('en_core_web_sm')



def main(args):

    # Grammar Correction: get grammar-corrected content
    gc_model = T5ForConditionalGeneration.from_pretrained(args.gc_model_name)
    gc_toker = AutoTokenizer.from_pretrained(args.gc_model_name)
    gc_model_input_ids = gc_toker(f"Fix the grammar: {args.content}", return_tensors="pt").input_ids
    gc_model_outputs = gc_model.generate(gc_model_input_ids, max_length=256)
    gc_content = gc_toker.decode(gc_model_outputs[0], skip_special_tokens=True)

    # Paraphrase Detection: determine the intent of the grammar-corrected content
    pd_model = SentenceTransformer(args.pd_model_name)
    input_embedding = pd_model.encode(gc_content, convert_to_tensor=True)
    similarities = {}
    max_intent = 0
    intent = ""
    for intent_category, intent_embedding_tensor in torch.load(args.intent_embeddings_path).items():
        intent_embedding_tensor.to(args.device)
        similarities[intent_category] = util.cos_sim(input_embedding, intent_embedding_tensor).mean().item()
        if similarities[intent_category] > max_intent:
            max_intent = similarities[intent_category]
            intent = intent_category

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

    output = {
        'has_date': has_date,
        'has_time': has_time,
        'is_wh_question': is_wh_question,
        'has_auxiliary_verb': has_auxiliary_verb,
        'has_inversion': has_inversion,
        'question': gc_content,
        'uncorrected_words': misspelled_words,
        'intent_scores': similarities,
        'intent': intent
    }

    action = conversation_state(args.state, intent)

    if action == "qa_date_time":

        dates = [ent.text for ent in doc.ents if ent.label_ == 'DATE']
        times = [ent.text for ent in doc.ents if ent.label_ == 'TIME']

        qa_pipeline = pipeline('question-answering', model=args.qa_model_name, tokenizer=args.qa_model_name)
        response, confidence = "Not sure what to answer", 0.0
        negative = qa_pipeline({ 'question': gc_content, 'context': args.negative_context })

        if negative['score'] > 0.1:
            confidence = f"(-){negative['score']}"
            # TODO: Find closest day not in negative context to make a suggestion
            response = f"""qa_model says "{negative['answer']}". That doesn't work. How about not {dates[0]}."""
        else:
            confidence = f"1"
            response = f"{dates[0]} might work, let me check with the team."
            output['poll'] = f"{dates[0]}/{times[0] if len(times)>0 else '10pm'}"

        output['response'] = response
        output['score'] = confidence,

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

def conversation_state(state, intent, last_poll=None):
    """ Returns indicator for what type of response the model should generate """

    if state == "initiated":
        if intent == "suggestion":
            return "qa_date_time"
        elif intent == "request":
            return "qa"

    #     elif intent == "request":
    #         print("Randomly sample a time from affirmative context to suggest")
    #         print("Make a poll in scheduling with sampled time")
    #         return "poll"
    #     else:
    #         print("response type not implemented")
    #         return "initiated"

    # elif state == "Polling":
    #     if intent == "Passes":
    #         print("Send Message requesting confirmation")
    #         return "Awaiting"
    #     if intent == "Fails":
    #         return conversation_state("Ready", "Begin")

    # elif state == "Awaiting":
    #     if intent == "Confirm":
    #         print('Sending Message "see you then"')
    #         print("Create server event, auto-interest those who confirmed")
    #         return "Scheduled"
    #     if intent == "Denied":
    #         return conversation_state("Ready", "Begin")

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
        type=str,
        help="The name of the pre-trained paraphrase detection model to load. This model is used to classify the goal of the user message content.",
        default="all-MiniLM-L6-v2",
        metavar=""
    )

    parser.add_argument(
        "--intent_embeddings_path",
        type=str,
        help="The path to the pre-computed embedding tensors torch save file.",
        default="intent_embeddings.pt",
        metavar=""
    )

    parser.add_argument(
        "--general_availability_context",
        type=str,
        help="The context to which the qa model should respond to general availability questions.",
        default="We are available Tuesday any time.\nWe are available Wednesday at 5.\nWe are available Friday at 9.",
        metavar=""
    )

    parser.add_argument(
        "--negative_context",
        type=str,
        help="The context to which the qa model will answer no to regarding scheduling suggestions.",
        default="We are unavailable Wednesday.",
        metavar=""
    )

    args = parser.parse_args()

    args.device = "cuda" if torch.cuda.is_available() else "cpu"

    main(args)
