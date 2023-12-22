import argparse
from dotenv import load_dotenv
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

    print("state:", args.state)
    conversation_state(args.state, "")

    grammar_model = T5ForConditionalGeneration.from_pretrained(args.grammar_model_name)
    grammar_toker = AutoTokenizer.from_pretrained(args.grammar_model_name)

    grammar_model_input_ids = grammar_toker(f"Fix the grammar: {args.content}", return_tensors="pt").input_ids
    grammar_model_outputs = grammar_model.generate(grammar_model_input_ids, max_length=256)
    edited_content = grammar_toker.decode(grammar_model_outputs[0], skip_special_tokens=True)

    doc = language_model(edited_content)

    for token in doc:
        if token.text not in spell_checker and not token.is_punct:
            corrected_word = spell_checker.correction(token.text)
            print(f"Mispelled: {token.text}? -> {corrected_word}")
    
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
    
    print("has_date:", has_date)
    print("has_time:", has_time)
    print("is_wh_question:", is_wh_question)
    print("has_auxiliary_verb:", has_auxiliary_verb)
    print("has_inversion:", has_inversion)

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
        if affirmative['score'] > 0.1 and response is None:
            response = affirmative

    if response is None:
        response = "Not sure, let me check with the dads"
    

    print(f"Q :\n{edited_content}")
    print(f"AC:\n{affirmative_context}")
    print(f"NC:\n{negative_context}")
    print(f"R :\n{response}")



def conversation_state(state, action, last_poll=None):

    if state == "initiated":
        if action == "":
            print("Randomly sample a time from affirmative context to suggest")
            print("Make a poll in scheduling with sampled time")
            return "Polling"

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
