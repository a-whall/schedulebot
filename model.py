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



load_dotenv()
league_entities = os.getenv('LEAGUE_ENTITIES').split(',')

spell_checker = SpellChecker()
language_model = spacy.load('en_core_web_sm')



def main(args):

    grammar_model = T5ForConditionalGeneration.from_pretrained(args.grammar_model_name)
    grammar_toker = AutoTokenizer.from_pretrained(args.grammar_model_name)

    grammar_model_input_ids = grammar_toker(f"Fix the grammar: {args.content}", return_tensors="pt").input_ids
    grammar_model_outputs = grammar_model.generate(grammar_model_input_ids, max_length=256)
    edited_content = grammar_toker.decode(grammar_model_outputs[0], skip_special_tokens=True)

    doc = language_model(edited_content)

    for token in doc:
        if token.text not in spell_checker and not token.is_punct:
            corrected_word = spell_checker.correction(token.text)
            #print(f"Mispelled: {token.text}? -> {corrected_word}")
    
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

    is_suggestion = has_date
    if is_suggestion:
        conversation_state(args.state, "suggestion")

    affirmative_context = 'Nothing is up.\nWe are available Tuesday any time.\nWe are available Wednesday at 5.\nWe are available Friday at 9.'
    negative_context = 'We are unavailable thursday.'

    qa_pipeline = pipeline('question-answering', model=args.qa_model_name, tokenizer=args.qa_model_name)

    response = None

    negative = qa_pipeline({ 'question': edited_content, 'context': negative_context })
    if negative['score'] > 0.1: #or not date_matches_answer:
        # suggest a different time
        response = negative

    if response is None:
        affirmative = qa_pipeline({ 'question': edited_content, 'context': affirmative_context })
        if affirmative['score'] > 0.1:
            response = affirmative

    if response is None:
        response = "Not sure, let me check with the dads"
    
    output = {
        'has_date': has_date,
        'has_time': has_time,
        'is_wh_question': is_wh_question,
        'has_auxiliary_verb': has_auxiliary_verb,
        'has_inversion': has_inversion,
        'question': edited_content,
        'response': response
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
        help="The name of the pre-trained Question-Answering model to load.",
        default="deepset/roberta-base-squad2",
        metavar=""
    )

    parser.add_argument(
        "--grammar_model_name",
        type=str,
        help="The name of the pre-trained grammar fixing model to load.",
        default="grammarly/coedit-large",
        metavar=""
    )

    main(parser.parse_args())
